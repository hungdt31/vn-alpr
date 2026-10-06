"""REST API.

Run:  uvicorn app.api.main:app --host 0.0.0.0 --port 8000
Env:  ALPR_CONFIG (default configs/pipeline.yaml), ALPR_DB (default data/alpr.db)
"""

from __future__ import annotations

import os
import time
from typing import Literal

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.db.repository import EventRepository


def create_app(pipeline=None, repo: EventRepository | None = None) -> FastAPI:
    """Pipeline and repository are created lazily so the app starts fast and tests can inject fakes."""
    app = FastAPI(title="VN-ALPR API", version="0.1.0")
    state = {"pipeline": pipeline, "repo": repo}

    def get_pipeline():
        if state["pipeline"] is None:
            from alpr.pipeline import ALPRPipeline

            state["pipeline"] = ALPRPipeline.from_config(os.getenv("ALPR_CONFIG", "configs/pipeline.yaml"))
        return state["pipeline"]

    def get_repo() -> EventRepository:
        if state["repo"] is None:
            state["repo"] = EventRepository(os.getenv("ALPR_DB", "data/alpr.db"))
        return state["repo"]

    async def read_image(file: UploadFile) -> np.ndarray:
        data = np.frombuffer(await file.read(), np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Cannot decode image")
        return img

    def recognize(img: np.ndarray) -> tuple[list, float]:
        t0 = time.perf_counter()
        results = get_pipeline().process_image(img)
        return results, (time.perf_counter() - t0) * 1000

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/recognize")
    async def recognize_endpoint(file: UploadFile = File(...)):
        results, ms = recognize(await read_image(file))
        return {"plates": [r.to_dict() for r in results], "latency_ms": round(ms, 1)}

    @app.post("/gate/{direction}")
    async def gate(direction: Literal["in", "out"], file: UploadFile = File(...), gate: str = "main"):
        """Recognize a gate snapshot and log every valid plate as an entry/exit."""
        results, ms = recognize(await read_image(file))
        events = []
        for r in results:
            if r.valid:
                ev = get_repo().add_event(r.text, r.display, direction, r.ocr_conf, gate=gate)
                if ev is not None:
                    events.append(ev)
        return {"plates": [r.to_dict() for r in results], "events": events, "latency_ms": round(ms, 1)}

    @app.get("/events")
    def events(plate: str | None = None, limit: int = Query(100, ge=1, le=1000)):
        from alpr.postprocess.plate_format import normalize

        return get_repo().list_events(normalize(plate) if plate else None, limit)

    @app.get("/parked")
    def parked():
        return get_repo().parked()

    return app


app = create_app()
