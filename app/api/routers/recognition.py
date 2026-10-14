"""/health and /recognize."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_recognition
from app.api.schemas import PlateOut, RecognizeOut
from app.services.recognition import RecognitionService

router = APIRouter(tags=["recognition"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/recognize", response_model=RecognizeOut)
async def recognize(file: UploadFile = File(...), recognition: RecognitionService = Depends(get_recognition)):
    plates, ms = recognition.read(recognition.decode(await file.read()))
    return RecognizeOut(plates=[PlateOut.model_validate(p) for p in plates], latency_ms=ms)
