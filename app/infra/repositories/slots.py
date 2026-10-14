"""Parking slots, one vehicle type each."""

from __future__ import annotations

from app.domain.models import Slot, slot_ids
from app.infra.db import Database


class SlotRepository:
    def __init__(self, db: Database):
        self.db = db

    def seed(self, layout: dict[str, int]) -> None:
        """Make sure the slots of the layout exist, e.g. {"motorbike": 20, "car": 10} -> M01..M20, C01..C10."""
        self.db.executemany(
            "INSERT OR IGNORE INTO slots (id, vehicle_type) VALUES (?, ?)",
            [(sid, kind) for kind, n in layout.items() for sid in slot_ids(kind, n)],
        )

    def all(self) -> list[Slot]:
        rows = self.db.all("SELECT * FROM slots ORDER BY vehicle_type DESC, id")
        return [Slot(id=r["id"], vehicle_type=r["vehicle_type"]) for r in rows]

    def first_free(self, vehicle_type: str) -> Slot | None:
        row = self.db.one(
            "SELECT * FROM slots WHERE vehicle_type = ? AND id NOT IN "
            "(SELECT slot_id FROM sessions WHERE status = 'parked') ORDER BY id LIMIT 1",
            (vehicle_type,),
        )
        return Slot(id=row["id"], vehicle_type=row["vehicle_type"]) if row else None
