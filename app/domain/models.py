"""Entities of the parking domain. Plain dataclasses: no SQL, no HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

VehicleType = Literal["motorbike", "car"]
Direction = Literal["in", "out"]
CardStatus = Literal["available", "in_use", "locked"]
SessionStatus = Literal["parked", "exited"]
MatchStatus = Literal["ok", "suspect", "mismatch"]

VEHICLE_TYPES: tuple[VehicleType, ...] = ("motorbike", "car")
VEHICLE_LABEL: dict[str, str] = {"motorbike": "xe máy", "car": "ô tô"}
SLOT_PREFIX: dict[str, str] = {"motorbike": "M", "car": "C"}


def card_code(card_id: int) -> str:
    """Printed ticket number: 1 -> T001."""
    return f"T{card_id:03d}"


def slot_ids(vehicle_type: str, count: int) -> list[str]:
    """M01..M20 for motorbikes, C01..C10 for cars."""
    return [f"{SLOT_PREFIX[vehicle_type]}{i:02d}" for i in range(1, count + 1)]


@dataclass
class Card:
    id: int
    status: CardStatus = "available"
    returned_at: datetime | None = None

    @property
    def code(self) -> str:
        return card_code(self.id)


@dataclass
class Slot:
    id: str
    vehicle_type: VehicleType


@dataclass
class Capture:
    """A gate camera snapshot and what the model read on it (PlateResult dicts)."""

    id: int
    path: str
    plates: list[dict]
    created_at: datetime


@dataclass
class Session:
    """One visit: from taking a ticket at the entry to leaving through the exit."""

    id: int
    card_id: int
    slot_id: str
    vehicle_type: VehicleType
    plate: str  # normalized, e.g. "54L19999"
    display: str  # as confirmed by the driver, e.g. "54-L1 9999" (keeps the 2-line layout)
    entry_time: datetime
    vehicle_style: dict = field(default_factory=dict)  # 3D look chosen in the UI
    plate_ocr: str = ""  # what the model read at the entry
    ocr_conf: float = 0.0
    edited: bool = False  # the driver corrected the model
    entry_capture: int | None = None
    entry_box: list[int] | None = None
    exit_capture: int | None = None
    exit_plate_ocr: str | None = None
    exit_match: MatchStatus | None = None
    exit_time: datetime | None = None
    fee: int | None = None
    lost_card: bool = False
    override_reason: str | None = None
    status: SessionStatus = "parked"

    @property
    def card_code(self) -> str:
        return card_code(self.card_id)


@dataclass
class GateEvent:
    """A line of the gate log (entries and exits seen by any camera)."""

    id: int
    plate: str
    display: str
    direction: Direction
    gate: str
    confidence: float
    created_at: datetime
    image_path: str | None = None
    duration_s: int | None = None  # only on an exit that follows an entry
