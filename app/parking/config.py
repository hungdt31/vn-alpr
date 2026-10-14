"""Parking lot configuration (configs/parking.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from alpr.config import _build

VEHICLE_TYPES = ("motorbike", "car")


@dataclass
class LotConfig:
    name: str = "Bãi giữ xe VN-ALPR"
    cards: int = 30
    slots: dict[str, int] = field(default_factory=lambda: {"motorbike": 20, "car": 10})


@dataclass
class FeeConfig:
    base: int = 5000
    base_hours: int = 4
    per_hour: int = 2000
    lost_card: int = 50000


@dataclass
class MatchConfig:
    max_suspect_distance: int = 1
    suspect_below_conf: float = 0.95


@dataclass
class ParkingConfig:
    lot: LotConfig = field(default_factory=LotConfig)
    fees: dict[str, FeeConfig] = field(
        default_factory=lambda: {
            "motorbike": FeeConfig(),
            "car": FeeConfig(base=30000, base_hours=2, per_hour=10000, lost_card=200000),
        }
    )
    matching: MatchConfig = field(default_factory=MatchConfig)
    db: str = "data/alpr.db"
    captures_dir: str = "data/captures"
    allow_time_travel: bool = False


def load_parking_config(path: str | Path) -> ParkingConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    top = _build(ParkingConfig, {k: v for k, v in raw.items() if k not in ("lot", "fees", "matching")})
    top.lot = _build(LotConfig, raw.get("lot"))
    top.matching = _build(MatchConfig, raw.get("matching"))
    if "fees" in raw:
        top.fees = {kind: _build(FeeConfig, raw["fees"].get(kind)) for kind in VEHICLE_TYPES}
    unknown = set(top.lot.slots) - set(VEHICLE_TYPES)
    if unknown:
        raise ValueError(f"Unknown vehicle types in lot.slots: {sorted(unknown)}")
    if top.lot.cards < sum(top.lot.slots.values()):
        raise ValueError("lot.cards must be at least the number of slots, or the lot can never fill up")
    return top
