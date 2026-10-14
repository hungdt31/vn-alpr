"""Shared test helpers (fixtures live in conftest.py)."""

from datetime import datetime, timedelta

from app.core.settings import LotLayout, ParkingSettings, Settings

T0 = datetime(2026, 10, 14, 8, 0, 0)


class FakeClock:
    """A clock the test moves by hand; also supports the demo fast-forward (advance)."""

    def __init__(self, start: datetime = T0):
        self.t = start
        self.offset = timedelta(0)

    def now(self) -> datetime:
        return self.t

    def advance(self, hours: float) -> datetime:
        self.t += timedelta(hours=hours)
        self.offset += timedelta(hours=hours)
        return self.t


def make_settings(tmp_path, cards=4, slots=None, time_travel=True) -> Settings:
    """A small lot (2 motorbikes, 1 car by default) in a throwaway database."""
    parking = ParkingSettings(
        lot=LotLayout(cards=cards, slots=slots or {"motorbike": 2, "car": 1}),
        captures_dir=str(tmp_path / "captures"),
        exports_dir=str(tmp_path / "corr"),
        allow_time_travel=time_travel,
    )
    return Settings(db=str(tmp_path / "test.db"), parking=parking)
