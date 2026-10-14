"""Clocks. Services ask a Clock for the time instead of calling datetime.now(), so tests can fix it and the
demo can fast-forward it."""

from __future__ import annotations

from datetime import datetime, timedelta


class SystemClock:
    def now(self) -> datetime:
        return datetime.now().replace(microsecond=0)


class OffsetClock:
    """Real time plus an offset that only moves forward (demo: show the fee of a long stay right away)."""

    def __init__(self, base: SystemClock | None = None):
        self._base = base or SystemClock()
        self.offset = timedelta(0)

    def now(self) -> datetime:
        return self._base.now() + self.offset

    def advance(self, hours: float) -> datetime:
        if hours <= 0:
            raise ValueError("the clock only moves forward")
        self.offset += timedelta(hours=hours)
        return self.now()
