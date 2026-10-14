"""REST routes for the parking lot simulation (/parking/*)."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.parking.export import export_line_dataset
from app.parking.lot import ParkingError, ParkingLot
from app.parking.rules import parse_plate_input


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
    out: str = "data/corrections/ocr"
    edited_only: bool = False


def parking_router(get_lot: Callable[[], ParkingLot], get_pipeline: Callable) -> APIRouter:
    r = APIRouter(prefix="/parking", tags=["parking"])

    def call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ParkingError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    @r.get("/lot")
    def lot_state():
        return get_lot().state()

    @r.get("/stats")
    def stats():
        return get_lot().stats()

    @r.get("/sessions")
    def sessions(status: Literal["parked", "exited"] | None = None, plate: str | None = None,
                 limit: int = Query(100, ge=1, le=1000)):
        return get_lot().sessions(status, plate, limit)

    @r.post("/captures")
    async def capture(file: UploadFile = File(...)):
        """Camera snapshot: run the model and keep the photo as evidence."""
        data = await file.read()
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Cannot decode image")
        t0 = time.perf_counter()
        plates = [p.to_dict() for p in get_pipeline().process_image(img)]
        latency = (time.perf_counter() - t0) * 1000
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        cap = get_lot().save_capture(jpg.tobytes(), plates)
        return {"capture": {k: v for k, v in cap.items() if k != "path"}, "latency_ms": round(latency, 1)}

    @r.get("/captures/{capture_id}/image")
    def capture_image(capture_id: int):
        path = Path(call(get_lot().get_capture, capture_id)["path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail="Image file missing")
        return FileResponse(path, media_type="image/jpeg")

    @r.post("/plates/validate")
    def validate(body: PlateText):
        p = parse_plate_input(body.text)
        return {"valid": p.valid, "text": p.text, "display": p.display}

    @r.post("/entry")
    def entry(body: EntryRequest):
        return call(get_lot().enter, body.card_id, body.plate, body.vehicle_type, body.capture_id, body.style)

    @r.post("/exit/check")
    def exit_check(body: ExitCheckRequest):
        lot = get_lot()
        if body.card_id is None and not body.plate:
            raise HTTPException(status_code=422, detail="Cần mã thẻ, hoặc biển số khi mất thẻ")
        session = call(lot.find_parked, card_id=body.card_id, plate=body.plate)
        return call(lot.check_exit, session["id"], body.capture_id, body.lost_card)

    @r.post("/exit/confirm")
    def exit_confirm(body: ExitConfirmRequest):
        return call(get_lot().confirm_exit, body.session_id, body.capture_id, body.lost_card, body.override_reason)

    @r.post("/cards/{card_id}/restore")
    def restore_card(card_id: int):
        call(get_lot().restore_card, card_id)
        return get_lot().state()["cards"]

    @r.post("/clock")
    def clock(body: ClockRequest):
        return {"now": call(get_lot().travel, body.hours).isoformat()}

    @r.post("/corrections/export")
    def export(body: ExportRequest):
        lot = get_lot()
        n = export_line_dataset(lot.labeled_captures(body.edited_only), body.out)
        return {"lines": n, "out": body.out}

    return r
