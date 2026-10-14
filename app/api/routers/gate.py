"""Gate cameras: /gate/{in,out}, /events, /parked."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.deps import get_gate_log, get_recognition
from app.api.schemas import EventOut, GateOut, PlateOut
from app.services.gate_log import GateLog
from app.services.recognition import RecognitionService

router = APIRouter(tags=["gate"])


@router.post("/gate/{direction}", response_model=GateOut)
async def gate(
    direction: Literal["in", "out"],
    file: UploadFile = File(...),
    gate: str = "main",
    recognition: RecognitionService = Depends(get_recognition),
    log: GateLog = Depends(get_gate_log),
):
    """Recognize a gate snapshot and log every valid plate as an entry/exit."""
    plates, ms = recognition.read(recognition.decode(await file.read()))
    events = [log.record(p.text, p.display, direction, p.ocr_conf, gate=gate) for p in plates if p.valid]
    return GateOut(
        plates=[PlateOut.model_validate(p) for p in plates],
        events=[EventOut.model_validate(e) for e in events if e is not None],
        latency_ms=ms,
    )


@router.get("/events", response_model=list[EventOut])
def events(plate: str | None = None, limit: int = Query(100, ge=1, le=1000), log: GateLog = Depends(get_gate_log)):
    return [EventOut.model_validate(e) for e in log.list(plate, limit)]


@router.get("/parked", response_model=list[EventOut])
def parked(log: GateLog = Depends(get_gate_log)):
    return [EventOut.model_validate(e) for e in log.parked()]
