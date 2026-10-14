"""Parking lot with tickets (cards), typed slots and parking sessions, stored in SQLite.

Entry:  capture() -> the driver checks/edits the plate -> next_card() -> enter()
Exit:   capture() -> check_exit() (plate on the ticket vs plate read now, fee) -> confirm_exit()
The exit plate is never typed by the driver: a mismatch needs a guard's override reason.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from alpr.metrics import levenshtein
from alpr.postprocess.plate_format import normalize
from app.parking.config import VEHICLE_TYPES, ParkingConfig
from app.parking.rules import match_exit_plate, parking_fee, parse_plate_input

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'in_use', 'locked')),
    returned_at TEXT
);
CREATE TABLE IF NOT EXISTS slots (
    id           TEXT PRIMARY KEY,
    vehicle_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS captures (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    path       TEXT NOT NULL,
    plates     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id         INTEGER NOT NULL REFERENCES cards (id),
    slot_id         TEXT NOT NULL REFERENCES slots (id),
    vehicle_type    TEXT NOT NULL,
    vehicle_style   TEXT NOT NULL DEFAULT '{}',
    plate           TEXT NOT NULL,
    display         TEXT NOT NULL,
    plate_ocr       TEXT NOT NULL DEFAULT '',
    ocr_conf        REAL NOT NULL DEFAULT 0,
    edited          INTEGER NOT NULL DEFAULT 0,
    entry_capture   INTEGER REFERENCES captures (id),
    entry_box       TEXT,
    entry_time      TEXT NOT NULL,
    exit_capture    INTEGER REFERENCES captures (id),
    exit_plate_ocr  TEXT,
    exit_match      TEXT,
    exit_time       TEXT,
    fee             INTEGER,
    lost_card       INTEGER NOT NULL DEFAULT 0,
    override_reason TEXT,
    status          TEXT NOT NULL DEFAULT 'parked' CHECK (status IN ('parked', 'exited'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_plate ON sessions (plate, status);
"""

TYPE_PREFIX = {"motorbike": "M", "car": "C"}


class ParkingError(Exception):
    """A business rule refused the request; status_code maps to the HTTP response."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def card_code(card_id: int) -> str:
    return f"T{card_id:03d}"


class ParkingLot:
    def __init__(self, cfg: ParkingConfig, now: Callable[[], datetime] = datetime.now, on_event=None):
        """now: injectable clock (tests). on_event(plate, display, direction, conf): optional gate log hook."""
        self.cfg = cfg
        self._now = now
        self.time_offset = timedelta(0)
        self.on_event = on_event
        self.captures_dir = Path(cfg.captures_dir)
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        Path(cfg.db).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(cfg.db, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()
        self._seed()

    def close(self) -> None:
        self._conn.close()

    def _seed(self) -> None:
        with self._lock:
            self._conn.executemany(
                "INSERT OR IGNORE INTO cards (id) VALUES (?)", [(i,) for i in range(1, self.cfg.lot.cards + 1)]
            )
            self._conn.executemany(
                "INSERT OR IGNORE INTO slots (id, vehicle_type) VALUES (?, ?)",
                [(f"{TYPE_PREFIX[kind]}{i:02d}", kind)
                 for kind, n in self.cfg.lot.slots.items() for i in range(1, n + 1)],
            )
            self._conn.commit()

    # ---- clock ------------------------------------------------------------------------------
    def now(self) -> datetime:
        return (self._now() + self.time_offset).replace(microsecond=0)

    def travel(self, hours: float) -> datetime:
        """Demo only: move the clock forward so fees for long stays can be shown."""
        if not self.cfg.allow_time_travel:
            raise ParkingError("Tua thời gian đang bị tắt (allow_time_travel: false)", 403)
        self.time_offset += timedelta(hours=hours)
        return self.now()

    # ---- captures ---------------------------------------------------------------------------
    def save_capture(self, image_bytes: bytes, plates: list[dict]) -> dict:
        """Keep the camera image and what the model read, as evidence for the guard and for retraining."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO captures (path, plates, created_at) VALUES ('', ?, ?)",
                (json.dumps(plates), self.now().isoformat()),
            )
            capture_id = cur.lastrowid
            path = self.captures_dir / f"{capture_id:06d}.jpg"
            path.write_bytes(image_bytes)
            self._conn.execute("UPDATE captures SET path = ? WHERE id = ?", (str(path), capture_id))
            self._conn.commit()
        return self.get_capture(capture_id)

    def get_capture(self, capture_id: int) -> dict:
        row = self._conn.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
        if row is None:
            raise ParkingError(f"Không có ảnh chụp #{capture_id}", 404)
        return {"id": row["id"], "path": row["path"], "plates": json.loads(row["plates"]),
                "created_at": row["created_at"]}

    # ---- lot state --------------------------------------------------------------------------
    def next_card(self) -> int | None:
        """Top of the dispenser: the card that has been back in the box the longest."""
        row = self._conn.execute(
            "SELECT id FROM cards WHERE status = 'available' ORDER BY returned_at IS NOT NULL, returned_at, id LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def state(self) -> dict:
        rows = self._conn.execute("SELECT status, COUNT(*) AS n FROM cards GROUP BY status")
        cards = {r["status"]: r["n"] for r in rows}
        parked = {r["slot_id"]: self._session_dict(r) for r in
                  self._conn.execute("SELECT * FROM sessions WHERE status = 'parked'")}
        slots = [{"id": r["id"], "vehicle_type": r["vehicle_type"], "session": parked.get(r["id"])}
                 for r in self._conn.execute("SELECT * FROM slots ORDER BY vehicle_type DESC, id")]
        nxt = self.next_card()
        locked = [r["id"] for r in self._conn.execute("SELECT id FROM cards WHERE status = 'locked' ORDER BY id")]
        return {
            "name": self.cfg.lot.name,
            "now": self.now().isoformat(),
            "time_offset_h": self.time_offset.total_seconds() / 3600,
            "allow_time_travel": self.cfg.allow_time_travel,
            "cards": {"available": cards.get("available", 0), "in_use": cards.get("in_use", 0),
                      "locked": cards.get("locked", 0), "locked_ids": locked,
                      "next": nxt, "next_code": card_code(nxt) if nxt else None},
            "capacity": {
                kind: {"total": n, "free": sum(1 for s in slots if s["vehicle_type"] == kind and not s["session"])}
                for kind, n in self.cfg.lot.slots.items()
            },
            "slots": slots,
            "fees": {kind: vars(fee) for kind, fee in self.cfg.fees.items()},
        }

    # ---- entry ------------------------------------------------------------------------------
    def enter(self, card_id: int, plate_text: str, vehicle_type: str, capture_id: int | None = None,
              style: dict | None = None) -> dict:
        if vehicle_type not in VEHICLE_TYPES:
            raise ParkingError(f"Loại xe không hợp lệ: {vehicle_type}", 422)
        plate = parse_plate_input(plate_text)
        if not plate.valid:
            raise ParkingError(f"'{plate_text}' không đúng định dạng biển số Việt Nam", 422)
        ocr_text, ocr_conf, box = "", 0.0, None
        if capture_id is not None:
            reads = self.get_capture(capture_id)["plates"]
            if reads:  # the plate the driver confirmed: the read closest to the final text
                best = min(reads, key=lambda p: levenshtein(normalize(p["text"]), plate.text))
                ocr_text, ocr_conf, box = normalize(best["text"]), float(best["ocr_conf"]), best["box"]
        with self._lock:
            if self._conn.execute("SELECT 1 FROM sessions WHERE plate = ? AND status = 'parked'",
                                  (plate.text,)).fetchone():
                raise ParkingError(f"Xe {plate.display} đang ở trong bãi, không thể gửi thêm lần nữa")
            card = self._conn.execute("SELECT status FROM cards WHERE id = ?", (card_id,)).fetchone()
            if card is None or card["status"] != "available":
                raise ParkingError(f"Thẻ {card_code(card_id)} không có trong thùng")
            slot = self._conn.execute(
                "SELECT id FROM slots WHERE vehicle_type = ? AND id NOT IN "
                "(SELECT slot_id FROM sessions WHERE status = 'parked') ORDER BY id LIMIT 1", (vehicle_type,)
            ).fetchone()
            if slot is None:
                raise ParkingError("Bãi đã hết chỗ cho " + ("ô tô" if vehicle_type == "car" else "xe máy"))
            cur = self._conn.execute(
                "INSERT INTO sessions (card_id, slot_id, vehicle_type, vehicle_style, plate, display, plate_ocr, "
                "ocr_conf, edited, entry_capture, entry_box, entry_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (card_id, slot["id"], vehicle_type, json.dumps(style or {}), plate.text, plate.display, ocr_text,
                 ocr_conf, int(ocr_text != plate.text),  # typed from scratch counts as a correction too
                 capture_id, json.dumps(box) if box else None, self.now().isoformat()),
            )
            self._conn.execute("UPDATE cards SET status = 'in_use' WHERE id = ?", (card_id,))
            self._conn.commit()
        session = self.get_session(cur.lastrowid)
        if self.on_event:
            self.on_event(plate.text, plate.display, "in", ocr_conf)
        return session

    # ---- exit -------------------------------------------------------------------------------
    def find_parked(self, card_id: int | None = None, plate: str | None = None) -> dict:
        if card_id is not None:
            row = self._conn.execute("SELECT * FROM sessions WHERE card_id = ? AND status = 'parked'",
                                     (card_id,)).fetchone()
            if row is None:
                raise ParkingError(f"Thẻ {card_code(card_id)} không gắn với xe nào trong bãi", 404)
        else:
            row = self._conn.execute("SELECT * FROM sessions WHERE plate = ? AND status = 'parked'",
                                     (normalize(plate or ""),)).fetchone()
            if row is None:
                raise ParkingError(f"Không có xe {plate} trong bãi", 404)
        return self._session_dict(row)

    def check_exit(self, session_id: int, capture_id: int, lost_card: bool = False) -> dict:
        """What the exit gate shows: plate on the ticket vs plate read now, and the fee. Changes nothing."""
        session = self.get_session(session_id)
        if session["status"] != "parked":
            raise ParkingError("Xe này đã ra khỏi bãi")
        capture = self.get_capture(capture_id)
        match = match_exit_plate(session["plate"], [(p["text"], p["ocr_conf"]) for p in capture["plates"]],
                                 self.cfg.matching)
        now = self.now()
        fee = parking_fee(self.cfg.fees[session["vehicle_type"]], datetime.fromisoformat(session["entry_time"]),
                          now, lost_card)
        return {"session": session, "capture": capture, "match": vars(match), "fee": fee, "lost_card": lost_card,
                "exit_time": now.isoformat(),
                "duration_s": int((now - datetime.fromisoformat(session["entry_time"])).total_seconds())}

    def confirm_exit(self, session_id: int, capture_id: int, lost_card: bool = False,
                     override_reason: str | None = None) -> dict:
        check = self.check_exit(session_id, capture_id, lost_card)
        status = check["match"]["status"]
        reason = (override_reason or "").strip() or None
        if status != "ok" and not reason:
            raise ParkingError("Biển số lúc ra không khớp với thẻ: bảo vệ phải kiểm tra và ghi lý do cho xe ra")
        session = check["session"]
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET status = 'exited', exit_capture = ?, exit_plate_ocr = ?, exit_match = ?, "
                "exit_time = ?, fee = ?, lost_card = ?, override_reason = ? WHERE id = ?",
                (capture_id, check["match"]["read"], status, check["exit_time"], check["fee"], int(lost_card),
                 reason, session_id),
            )
            if lost_card:  # the missing ticket must never open the gate again
                self._conn.execute("UPDATE cards SET status = 'locked' WHERE id = ?", (session["card_id"],))
            else:
                self._conn.execute("UPDATE cards SET status = 'available', returned_at = ? WHERE id = ?",
                                   (check["exit_time"], session["card_id"]))
            self._conn.commit()
        if self.on_event:
            self.on_event(session["plate"], session["display"], "out", 1.0)
        return self.get_session(session_id)

    def restore_card(self, card_id: int) -> None:
        """A lost ticket was found (or replaced): put it back in the dispenser."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE cards SET status = 'available', returned_at = ? WHERE id = ? AND status = 'locked'",
                (self.now().isoformat(), card_id))
            self._conn.commit()
        if cur.rowcount == 0:
            raise ParkingError(f"Thẻ {card_code(card_id)} không ở trạng thái bị khoá", 404)

    # ---- sessions & stats -------------------------------------------------------------------
    def _session_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["vehicle_style"] = json.loads(d["vehicle_style"] or "{}")
        d["entry_box"] = json.loads(d["entry_box"]) if d["entry_box"] else None
        d["card_code"] = card_code(d["card_id"])
        d["edited"] = bool(d["edited"])
        d["lost_card"] = bool(d["lost_card"])
        return d

    def get_session(self, session_id: int) -> dict:
        row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise ParkingError(f"Không có lượt gửi #{session_id}", 404)
        return self._session_dict(row)

    def sessions(self, status: str | None = None, plate: str | None = None, limit: int = 100) -> list[dict]:
        sql, args = "SELECT * FROM sessions WHERE 1 = 1", []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if plate:
            sql += " AND plate LIKE ?"
            args.append(f"%{normalize(plate)}%")
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [self._session_dict(r) for r in self._conn.execute(sql, args)]

    def stats(self) -> dict:
        today = self.now().date().isoformat()
        q = lambda sql, *a: self._conn.execute(sql, a).fetchone()[0]  # noqa: E731
        entries = q("SELECT COUNT(*) FROM sessions")
        with_photo = q("SELECT COUNT(*) FROM sessions WHERE entry_capture IS NOT NULL")
        edited = q("SELECT COUNT(*) FROM sessions WHERE entry_capture IS NOT NULL AND edited = 1")
        return {
            "parked": {kind: q("SELECT COUNT(*) FROM sessions WHERE status = 'parked' AND vehicle_type = ?", kind)
                       for kind in self.cfg.lot.slots},
            "today": {
                "entries": q("SELECT COUNT(*) FROM sessions WHERE substr(entry_time, 1, 10) = ?", today),
                "exits": q("SELECT COUNT(*) FROM sessions WHERE substr(exit_time, 1, 10) = ?", today),
                "revenue": q("SELECT COALESCE(SUM(fee), 0) FROM sessions WHERE substr(exit_time, 1, 10) = ?", today),
            },
            "revenue_total": q("SELECT COALESCE(SUM(fee), 0) FROM sessions"),
            "entries_total": entries,
            # share of plates the driver had to correct: a field estimate of the model's error rate
            "ocr_edit_rate": edited / with_photo if with_photo else None,
            "corrections": edited,
            "overrides": q("SELECT COUNT(*) FROM sessions WHERE override_reason IS NOT NULL"),
            "lost_cards": q("SELECT COUNT(*) FROM cards WHERE status = 'locked'"),
        }

    def labeled_captures(self, edited_only: bool = False) -> list[dict]:
        """Entry photos with the plate the driver confirmed: free training labels for the OCR model."""
        sql = ("SELECT s.plate, s.display, s.plate_ocr, s.edited, s.entry_box, c.path FROM sessions s "
               "JOIN captures c ON c.id = s.entry_capture WHERE s.entry_box IS NOT NULL")
        if edited_only:
            sql += " AND s.edited = 1"
        return [{**dict(r), "entry_box": json.loads(r["entry_box"])} for r in self._conn.execute(sql)]
