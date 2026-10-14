"""Parking tickets (cards)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.domain.models import Card, CardStatus
from app.infra.db import Database
from app.infra.repositories._rows import from_iso, to_iso


def _card(row: sqlite3.Row) -> Card:
    return Card(id=row["id"], status=row["status"], returned_at=from_iso(row["returned_at"]))


class CardRepository:
    def __init__(self, db: Database):
        self.db = db

    def seed(self, count: int) -> None:
        """Make sure tickets 1..count exist (new ones start in the dispenser)."""
        self.db.executemany("INSERT OR IGNORE INTO cards (id) VALUES (?)", [(i,) for i in range(1, count + 1)])

    def get(self, card_id: int) -> Card | None:
        row = self.db.one("SELECT * FROM cards WHERE id = ?", (card_id,))
        return _card(row) if row else None

    def next_available(self) -> Card | None:
        """Top of the dispenser: the card that has been back in the box the longest."""
        row = self.db.one(
            "SELECT * FROM cards WHERE status = 'available' ORDER BY returned_at IS NOT NULL, returned_at, id LIMIT 1"
        )
        return _card(row) if row else None

    def count_by_status(self) -> dict[str, int]:
        return {r["status"]: r["n"] for r in self.db.all("SELECT status, COUNT(*) AS n FROM cards GROUP BY status")}

    def locked_ids(self) -> list[int]:
        return [r["id"] for r in self.db.all("SELECT id FROM cards WHERE status = 'locked' ORDER BY id")]

    def set_status(self, card_id: int, status: CardStatus, returned_at: datetime | None = None) -> None:
        if returned_at is None:
            self.db.execute("UPDATE cards SET status = ? WHERE id = ?", (status, card_id))
        else:
            self.db.execute("UPDATE cards SET status = ?, returned_at = ? WHERE id = ?",
                            (status, to_iso(returned_at), card_id))
