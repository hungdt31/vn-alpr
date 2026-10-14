"""Conversions between SQLite values and domain values."""

from __future__ import annotations

from datetime import datetime


def to_iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def from_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
