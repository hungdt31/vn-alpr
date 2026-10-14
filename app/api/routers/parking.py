"""Parking lot simulation: /parking/*."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_parking, get_recognition
from app.api.schemas import (
    CaptureOut,
    CaptureResponse,
    CardsOut,
    ClockOut,
    ClockRequest,
    EntryRequest,
    ExitCheckOut,
    ExitCheckRequest,
    ExitConfirmRequest,
    ExportOut,
    ExportRequest,
    LotStateOut,
    PlateCheckOut,
    PlateText,
    SessionOut,
    StatsOut,
)
from app.domain.matching import parse_plate_input
from app.services.parking import ParkingService
from app.services.recognition import RecognitionService
from app.services.training_export import export_line_dataset

# Services return dataclasses; each route converts them with model_validate. Returning the dataclass itself would
# make FastAPI run dataclasses.asdict() first, which drops properties such as Session.card_code.
router = APIRouter(prefix="/parking", tags=["parking"])


@router.get("/lot", response_model=LotStateOut)
def lot_state(parking: ParkingService = Depends(get_parking)):
    return LotStateOut.model_validate(parking.state())


@router.get("/stats", response_model=StatsOut)
def stats(parking: ParkingService = Depends(get_parking)):
    return StatsOut.model_validate(parking.stats())


@router.get("/sessions", response_model=list[SessionOut])
def sessions(
    status: Literal["parked", "exited"] | None = None,
    plate: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    parking: ParkingService = Depends(get_parking),
):
    return [SessionOut.model_validate(s) for s in parking.list_sessions(status, plate, limit)]


@router.post("/captures", response_model=CaptureResponse)
async def capture(
    file: UploadFile = File(...),
    recognition: RecognitionService = Depends(get_recognition),
    parking: ParkingService = Depends(get_parking),
):
    """Camera snapshot: run the model and keep the photo as evidence."""
    img = recognition.decode(await file.read())
    plates, ms = recognition.read(img)
    saved = parking.save_capture(recognition.encode_jpeg(img), [p.to_dict() for p in plates])
    return CaptureResponse(capture=CaptureOut.model_validate(saved), latency_ms=ms)


@router.get("/captures/{capture_id}/image")
def capture_image(capture_id: int, parking: ParkingService = Depends(get_parking)):
    path = Path(parking.get_capture(capture_id).path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file missing")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/plates/validate", response_model=PlateCheckOut)
def validate(body: PlateText):
    plate = parse_plate_input(body.text)
    return PlateCheckOut(valid=plate.valid, text=plate.text, display=plate.display)


@router.post("/entry", response_model=SessionOut)
def entry(body: EntryRequest, parking: ParkingService = Depends(get_parking)):
    return SessionOut.model_validate(
        parking.enter(body.card_id, body.plate, body.vehicle_type, body.capture_id, body.style)
    )


@router.post("/exit/check", response_model=ExitCheckOut)
def exit_check(body: ExitCheckRequest, parking: ParkingService = Depends(get_parking)):
    session = parking.find_parked(card_id=body.card_id, plate=body.plate)
    return ExitCheckOut.model_validate(parking.check_exit(session.id, body.capture_id, body.lost_card))


@router.post("/exit/confirm", response_model=SessionOut)
def exit_confirm(body: ExitConfirmRequest, parking: ParkingService = Depends(get_parking)):
    return SessionOut.model_validate(
        parking.confirm_exit(body.session_id, body.capture_id, body.lost_card, body.override_reason)
    )


@router.post("/cards/{card_id}/restore", response_model=CardsOut)
def restore_card(card_id: int, parking: ParkingService = Depends(get_parking)):
    return CardsOut.model_validate(parking.restore_card(card_id))


@router.post("/clock", response_model=ClockOut)
def clock(body: ClockRequest, parking: ParkingService = Depends(get_parking)):
    return ClockOut(now=parking.travel(body.hours))


@router.post("/corrections/export", response_model=ExportOut)
def export(body: ExportRequest, parking: ParkingService = Depends(get_parking)):
    lines = export_line_dataset(parking.labeled_entries(body.edited_only), body.out)
    return ExportOut(lines=lines, out=body.out)
