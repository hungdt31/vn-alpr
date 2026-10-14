"""Gate log: entries and exits seen by the gate cameras (API /gate, run_camera.py, parking lot)."""

from __future__ import annotations

from datetime import datetime, timedelta

from alpr.postprocess.plate_format import normalize
from app.core.errors import Invalid
from app.domain.models import GateEvent
from app.infra.db import Database
from app.infra.repositories.events import EventRepository
from app.services.ports import Clock


class GateLog:
    def __init__(self, db: Database, events: EventRepository, clock: Clock, cooldown_s: float = 60.0):
        """cooldown_s: a repeated (plate, direction) within this window is the same vehicle read twice."""
        self.db = db
        self.events = events
        self.clock = clock
        self.cooldown = timedelta(seconds=cooldown_s)

    def record(self, plate: str, display: str, direction: str, confidence: float, gate: str = "main",
               image_path: str | None = None, ts: datetime | None = None) -> GateEvent | None:
        """Log an entry or exit. Returns None when it repeats the previous event within the cooldown.
        An exit right after an entry gets `duration_s`."""
        if direction not in ("in", "out"):
            raise Invalid("direction must be 'in' or 'out'")
        ts = ts or self.clock.now()
        with self.db.transaction():
            last = self.events.last_for_plate(plate)
            if last and last.direction == direction and ts - last.created_at < self.cooldown:
                return None
            event = self.events.add(plate, display, direction, gate, confidence, ts, image_path)
        if direction == "out" and last and last.direction == "in":
            event.duration_s = int((ts - last.created_at).total_seconds())
        return event

    def list(self, plate: str | None = None, limit: int = 100) -> list[GateEvent]:
        return self.events.list(normalize(plate) if plate else None, limit)

    def parked(self) -> list[GateEvent]:
        return self.events.parked()
