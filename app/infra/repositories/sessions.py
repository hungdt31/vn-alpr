"""Parking visits (sessions) and the queries behind the guard's dashboard."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from app.domain.models import Session
from app.infra.db import Database
from app.infra.repositories._rows import from_iso, to_iso


def _session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"], card_id=row["card_id"], slot_id=row["slot_id"], vehicle_type=row["vehicle_type"],
        vehicle_style=json.loads(row["vehicle_style"] or "{}"), plate=row["plate"], display=row["display"],
        plate_ocr=row["plate_ocr"], ocr_conf=row["ocr_conf"], edited=bool(row["edited"]),
        entry_capture=row["entry_capture"], entry_box=json.loads(row["entry_box"]) if row["entry_box"] else None,
        entry_time=from_iso(row["entry_time"]), exit_capture=row["exit_capture"],
        exit_plate_ocr=row["exit_plate_ocr"], exit_match=row["exit_match"], exit_time=from_iso(row["exit_time"]),
        fee=row["fee"], lost_card=bool(row["lost_card"]), override_reason=row["override_reason"],
        status=row["status"],
    )


class SessionRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, s: Session) -> int:
        """Store a new visit (s.id is ignored) and return its id."""
        cur = self.db.execute(
            "INSERT INTO sessions (card_id, slot_id, vehicle_type, vehicle_style, plate, display, plate_ocr, "
            "ocr_conf, edited, entry_capture, entry_box, entry_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (s.card_id, s.slot_id, s.vehicle_type, json.dumps(s.vehicle_style), s.plate, s.display, s.plate_ocr,
             s.ocr_conf, int(s.edited), s.entry_capture, json.dumps(s.entry_box) if s.entry_box else None,
             to_iso(s.entry_time)),
        )
        return cur.lastrowid

    def save_exit(self, s: Session) -> None:
        self.db.execute(
            "UPDATE sessions SET status = ?, exit_capture = ?, exit_plate_ocr = ?, exit_match = ?, exit_time = ?, "
            "fee = ?, lost_card = ?, override_reason = ? WHERE id = ?",
            (s.status, s.exit_capture, s.exit_plate_ocr, s.exit_match, to_iso(s.exit_time), s.fee, int(s.lost_card),
             s.override_reason, s.id),
        )

    def get(self, session_id: int) -> Session | None:
        row = self.db.one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        return _session(row) if row else None

    def parked_with_card(self, card_id: int) -> Session | None:
        row = self.db.one("SELECT * FROM sessions WHERE card_id = ? AND status = 'parked'", (card_id,))
        return _session(row) if row else None

    def parked_with_plate(self, plate: str) -> Session | None:
        row = self.db.one("SELECT * FROM sessions WHERE plate = ? AND status = 'parked'", (plate,))
        return _session(row) if row else None

    def parked(self) -> list[Session]:
        return [_session(r) for r in self.db.all("SELECT * FROM sessions WHERE status = 'parked'")]

    def list(self, status: str | None = None, plate_like: str | None = None, limit: int = 100) -> list[Session]:
        sql, args = "SELECT * FROM sessions WHERE 1 = 1", []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if plate_like:
            sql += " AND plate LIKE ?"
            args.append(f"%{plate_like}%")
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [_session(r) for r in self.db.all(sql, args)]

    def labeled_entries(self, edited_only: bool = False) -> list[dict]:
        """Entry photos with the plate the driver confirmed (plate, display, entry_box, path)."""
        sql = ("SELECT s.plate, s.display, s.plate_ocr, s.edited, s.entry_box, c.path FROM sessions s "
               "JOIN captures c ON c.id = s.entry_capture WHERE s.entry_box IS NOT NULL")
        if edited_only:
            sql += " AND s.edited = 1"
        return [{**dict(r), "entry_box": json.loads(r["entry_box"])} for r in self.db.all(sql)]

    # ---- dashboard numbers --------------------------------------------------------------------
    def count_parked(self, vehicle_type: str) -> int:
        return self.db.scalar("SELECT COUNT(*) FROM sessions WHERE status = 'parked' AND vehicle_type = ?",
                              (vehicle_type,))

    def day_totals(self, day: date) -> dict[str, int]:
        d = day.isoformat()
        return {
            "entries": self.db.scalar("SELECT COUNT(*) FROM sessions WHERE substr(entry_time, 1, 10) = ?", (d,)),
            "exits": self.db.scalar("SELECT COUNT(*) FROM sessions WHERE substr(exit_time, 1, 10) = ?", (d,)),
            "revenue": self.db.scalar(
                "SELECT COALESCE(SUM(fee), 0) FROM sessions WHERE substr(exit_time, 1, 10) = ?", (d,)),
        }

    def totals(self) -> dict[str, int]:
        return {
            "entries": self.db.scalar("SELECT COUNT(*) FROM sessions"),
            "revenue": self.db.scalar("SELECT COALESCE(SUM(fee), 0) FROM sessions"),
            "with_photo": self.db.scalar("SELECT COUNT(*) FROM sessions WHERE entry_capture IS NOT NULL"),
            "corrections": self.db.scalar(
                "SELECT COUNT(*) FROM sessions WHERE entry_capture IS NOT NULL AND edited = 1"),
            "overrides": self.db.scalar("SELECT COUNT(*) FROM sessions WHERE override_reason IS NOT NULL"),
        }
