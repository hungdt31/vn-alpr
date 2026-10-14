"""Parking fee."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Tariff:
    """Price list of one vehicle type (configs/parking.yaml, `fees`)."""

    base: int = 5000  # for the first base_hours
    base_hours: int = 4
    per_hour: int = 2000  # every started hour after that
    lost_card: int = 50000  # added when the ticket is lost


def parking_fee(tariff: Tariff, entry: datetime, exit_: datetime, lost_card: bool = False) -> int:
    """base for the first base_hours, then per_hour for every started hour after; never below base."""
    hours = max(0.0, (exit_ - entry).total_seconds() / 3600)
    extra_hours = max(0, math.ceil(hours - tariff.base_hours - 1e-9))
    return tariff.base + extra_hours * tariff.per_hour + (tariff.lost_card if lost_card else 0)
