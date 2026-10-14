"""All application settings in one object: environment variables + configs/parking.yaml.

Env:  ALPR_CONFIG          pipeline config      (default configs/pipeline.yaml)
      ALPR_PARKING_CONFIG  parking lot config   (default configs/parking.yaml)
      ALPR_DB              SQLite database      (default: `db` in the parking config)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from alpr.config import _build
from app.domain.matching import MatchPolicy
from app.domain.models import VEHICLE_TYPES
from app.domain.pricing import Tariff


@dataclass
class LotLayout:
    name: str = "Bãi giữ xe VN-ALPR"
    cards: int = 30  # tickets in the dispenser
    slots: dict[str, int] = field(default_factory=lambda: {"motorbike": 20, "car": 10})


@dataclass
class ParkingSettings:
    """configs/parking.yaml. Every key in the file must exist here."""

    lot: LotLayout = field(default_factory=LotLayout)
    fees: dict[str, Tariff] = field(
        default_factory=lambda: {
            "motorbike": Tariff(),
            "car": Tariff(base=30000, base_hours=2, per_hour=10000, lost_card=200000),
        }
    )
    matching: MatchPolicy = field(default_factory=MatchPolicy)
    db: str = "data/alpr.db"
    captures_dir: str = "data/captures"
    allow_time_travel: bool = False  # demo only: fast-forward the clock to show fees


def load_parking_settings(path: str | Path) -> ParkingSettings:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    nested = ("lot", "fees", "matching")
    s = _build(ParkingSettings, {k: v for k, v in raw.items() if k not in nested})
    s.lot = _build(LotLayout, raw.get("lot"))
    s.matching = _build(MatchPolicy, raw.get("matching"))
    if "fees" in raw:
        s.fees = {kind: _build(Tariff, raw["fees"].get(kind)) for kind in VEHICLE_TYPES}
    unknown = set(s.lot.slots) - set(VEHICLE_TYPES)
    if unknown:
        raise ValueError(f"Unknown vehicle types in lot.slots: {sorted(unknown)}")
    if s.lot.cards < sum(s.lot.slots.values()):
        raise ValueError("lot.cards must be at least the number of slots, or the lot can never fill up")
    return s


@dataclass
class Settings:
    pipeline_config: str = "configs/pipeline.yaml"
    db: str = "data/alpr.db"
    gate_cooldown_s: float = 60.0  # a repeated (plate, direction) within this window is the same car read twice
    parking: ParkingSettings = field(default_factory=ParkingSettings)

    @classmethod
    def from_env(cls) -> Settings:
        parking = load_parking_settings(os.getenv("ALPR_PARKING_CONFIG", "configs/parking.yaml"))
        return cls(
            pipeline_config=os.getenv("ALPR_CONFIG", "configs/pipeline.yaml"),
            db=os.getenv("ALPR_DB", parking.db),
            parking=parking,
        )
