"""Gate entry/exit log (SQLite)."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plate       TEXT NOT NULL,
    display     TEXT NOT NULL,
    direction   TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    gate        TEXT NOT NULL DEFAULT 'main',
    confidence  REAL NOT NULL,
    image_path  TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_plate ON events (plate, created_at);
"""


class EventRepository:
    def __init__(self, path: str | Path = "data/alpr.db", cooldown_s: float = 60.0):
        """cooldown_s: ignore a repeated (plate, direction) within this window (same car read twice)."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()
        self.cooldown = timedelta(seconds=cooldown_s)

    def close(self) -> None:
        self._conn.close()

    def last_event(self, plate: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM events WHERE plate = ? ORDER BY created_at DESC, id DESC LIMIT 1", (plate,)
        ).fetchone()
        return dict(row) if row else None

    def add_event(
        self,
        plate: str,
        display: str,
        direction: str,
        confidence: float,
        gate: str = "main",
        image_path: str | None = None,
        ts: datetime | None = None,
    ) -> dict | None:
        """Insert an event; returns it (with `duration_s` for an exit after an entry) or None if deduplicated."""
        if direction not in ("in", "out"):
            raise ValueError("direction must be 'in' or 'out'")
        ts = ts or datetime.now()
        with self._lock:
            last = self.last_event(plate)
            if last and last["direction"] == direction:
                if ts - datetime.fromisoformat(last["created_at"]) < self.cooldown:
                    return None
            cur = self._conn.execute(
                "INSERT INTO events (plate, display, direction, gate, confidence, image_path, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (plate, display, direction, gate, float(confidence), image_path, ts.isoformat(timespec="seconds")),
            )
            self._conn.commit()
        event = dict(self._conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone())
        if direction == "out" and last and last["direction"] == "in":
            event["duration_s"] = int((ts - datetime.fromisoformat(last["created_at"])).total_seconds())
        return event

    def list_events(self, plate: str | None = None, limit: int = 100) -> list[dict]:
        if plate:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE plate LIKE ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (f"%{plate}%", limit),
            )
        else:
            rows = self._conn.execute("SELECT * FROM events ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def parked(self) -> list[dict]:
        """Vehicles whose latest event is an entry."""
        rows = self._conn.execute(
            """
            SELECT e.* FROM events e
            JOIN (SELECT plate, MAX(id) AS max_id FROM events GROUP BY plate) last ON e.id = last.max_id
            WHERE e.direction = 'in'
            ORDER BY e.created_at DESC
            """
        )
        return [dict(r) for r in rows]
