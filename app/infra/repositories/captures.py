"""Gate camera snapshots: where the image is and what the model read on it."""

from __future__ import annotations

import json
from datetime import datetime

from app.domain.models import Capture
from app.infra.db import Database
from app.infra.repositories._rows import from_iso, to_iso


class CaptureRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, plates: list[dict], created_at: datetime) -> int:
        """Reserve an id; the image path is set once the file is written (it is named after the id)."""
        cur = self.db.execute(
            "INSERT INTO captures (path, plates, created_at) VALUES ('', ?, ?)",
            (json.dumps(plates), to_iso(created_at)),
        )
        return cur.lastrowid

    def set_path(self, capture_id: int, path: str) -> None:
        self.db.execute("UPDATE captures SET path = ? WHERE id = ?", (path, capture_id))

    def get(self, capture_id: int) -> Capture | None:
        row = self.db.one("SELECT * FROM captures WHERE id = ?", (capture_id,))
        if row is None:
            return None
        return Capture(id=row["id"], path=row["path"], plates=json.loads(row["plates"]),
                       created_at=from_iso(row["created_at"]))
