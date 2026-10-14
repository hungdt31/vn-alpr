"""Gate log table (events)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.domain.models import GateEvent
from app.infra.db import Database
from app.infra.repositories._rows import from_iso, to_iso


def _event(row: sqlite3.Row) -> GateEvent:
    return GateEvent(
        id=row["id"], plate=row["plate"], display=row["display"], direction=row["direction"], gate=row["gate"],
        confidence=row["confidence"], image_path=row["image_path"], created_at=from_iso(row["created_at"]),
    )


class EventRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, plate: str, display: str, direction: str, gate: str, confidence: float, created_at: datetime,
            image_path: str | None = None) -> GateEvent:
        cur = self.db.execute(
            "INSERT INTO events (plate, display, direction, gate, confidence, image_path, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (plate, display, direction, gate, float(confidence), image_path, to_iso(created_at)),
        )
        return self.get(cur.lastrowid)

    def get(self, event_id: int) -> GateEvent:
        return _event(self.db.one("SELECT * FROM events WHERE id = ?", (event_id,)))

    def last_for_plate(self, plate: str) -> GateEvent | None:
        row = self.db.one("SELECT * FROM events WHERE plate = ? ORDER BY created_at DESC, id DESC LIMIT 1", (plate,))
        return _event(row) if row else None

    def list(self, plate_like: str | None = None, limit: int = 100) -> list[GateEvent]:
        if plate_like:
            rows = self.db.all(
                "SELECT * FROM events WHERE plate LIKE ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (f"%{plate_like}%", limit),
            )
        else:
            rows = self.db.all("SELECT * FROM events ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))
        return [_event(r) for r in rows]

    def parked(self) -> list[GateEvent]:
        """Vehicles whose latest event is an entry."""
        rows = self.db.all(
            """
            SELECT e.* FROM events e
            JOIN (SELECT plate, MAX(id) AS max_id FROM events GROUP BY plate) last ON e.id = last.max_id
            WHERE e.direction = 'in'
            ORDER BY e.created_at DESC
            """
        )
        return [_event(r) for r in rows]
