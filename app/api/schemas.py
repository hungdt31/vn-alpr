"""Request and response bodies. Responses are declared too, so OpenAPI (/docs) describes every field."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Out(BaseModel):
    """Responses are built straight from service dataclasses."""

    model_config = ConfigDict(from_attributes=True)


# ---- recognition & gate log ------------------------------------------------------------------
class PlateOut(Out):
    box: list[int]  # x1, y1, x2, y2 in image pixels
    det_conf: float
    text: str  # normalized, e.g. "51G12345"
    display: str  # human readable, e.g. "51G-123.45"
    ocr_conf: float
    valid: bool  # matches a VN plate template
    two_line: bool
    raw_lines: list[str]
    track_id: int | None = None


class RecognizeOut(Out):
    plates: list[PlateOut]
    latency_ms: float


class EventOut(Out):
    id: int
    plate: str
    display: str
    direction: Literal["in", "out"]
    gate: str
    confidence: float
    image_path: str | None
    created_at: datetime
    duration_s: int | None = None  # only on an exit that follows an entry


class GateOut(RecognizeOut):
    events: list[EventOut]


# ---- parking ---------------------------------------------------------------------------------
class SessionOut(Out):
    id: int
    card_id: int
    card_code: str
    slot_id: str
    vehicle_type: Literal["motorbike", "car"]
    vehicle_style: dict
    plate: str
    display: str
    plate_ocr: str
    ocr_conf: float
    edited: bool
    entry_capture: int | None
    entry_box: list[int] | None
    entry_time: datetime
    exit_capture: int | None
    exit_plate_ocr: str | None
    exit_match: Literal["ok", "suspect", "mismatch"] | None
    exit_time: datetime | None
    fee: int | None
    lost_card: bool
    override_reason: str | None
    status: Literal["parked", "exited"]


class CaptureOut(Out):
    id: int
    plates: list[PlateOut]
    created_at: datetime


class CaptureResponse(Out):
    capture: CaptureOut
    latency_ms: float


class CardsOut(Out):
    available: int
    in_use: int
    locked: int
    locked_ids: list[int]
    next: int | None
    next_code: str | None


class CapacityOut(Out):
    total: int
    free: int


class SlotOut(Out):
    id: str
    vehicle_type: Literal["motorbike", "car"]
    session: SessionOut | None


class TariffOut(Out):
    base: int
    base_hours: int
    per_hour: int
    lost_card: int


class LotStateOut(Out):
    name: str
    now: datetime
    time_offset_h: float
    allow_time_travel: bool
    cards: CardsOut
    capacity: dict[str, CapacityOut]
    slots: list[SlotOut]
    fees: dict[str, TariffOut]


class MatchOut(Out):
    status: Literal["ok", "suspect", "mismatch"]
    read: str
    distance: int
    reason: str


class ExitCheckOut(Out):
    session: SessionOut
    capture: CaptureOut
    match: MatchOut
    fee: int
    lost_card: bool
    exit_time: datetime
    duration_s: int


class DayTotalsOut(Out):
    entries: int
    exits: int
    revenue: int


class StatsOut(Out):
    parked: dict[str, int]
    today: DayTotalsOut
    revenue_total: int
    entries_total: int
    ocr_edit_rate: float | None
    corrections: int
    overrides: int
    lost_cards: int


class PlateCheckOut(Out):
    valid: bool
    text: str
    display: str


class ClockOut(Out):
    now: datetime


class ExportOut(Out):
    lines: int
    out: str


# ---- requests --------------------------------------------------------------------------------
class PlateText(BaseModel):
    text: str


class EntryRequest(BaseModel):
    card_id: int
    plate: str
    vehicle_type: Literal["motorbike", "car"]
    capture_id: int | None = None
    style: dict = Field(default_factory=dict)  # 3D look chosen in the UI: model, color


class ExitCheckRequest(BaseModel):
    capture_id: int
    card_id: int | None = None  # normal exit: the ticket
    plate: str | None = None  # lost ticket: look the vehicle up by plate
    lost_card: bool = False


class ExitConfirmRequest(BaseModel):
    session_id: int
    capture_id: int
    lost_card: bool = False
    override_reason: str | None = None


class ClockRequest(BaseModel):
    hours: float


class ExportRequest(BaseModel):
    # no output path here: a path chosen by the caller would let anyone write files anywhere on the server
    edited_only: bool = False
