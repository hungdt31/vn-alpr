"""REST API.

Run:  uvicorn app.api.main:app --host 0.0.0.0 --port 8000
Env:  see app/core/settings.py (ALPR_CONFIG, ALPR_PARKING_CONFIG, ALPR_DB, ALPR_PRELOAD, ALPR_WEB_DIR)

Layers: api (routers, schemas) -> services (use cases) -> domain (rules) / infra (SQLite, files, clock).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import gate, parking, recognition
from app.container import Container, build_container
from app.core.errors import AppError


def create_app(container: Container | None = None, web_dir: str | None = None) -> FastAPI:
    """container: None wires everything from the environment when the server starts (the pipeline itself loads on
    the first request unless ALPR_PRELOAD=1); tests pass build_container(settings, pipeline=FakePipeline()).
    web_dir: the built web UI to serve at / (production image); in development Vite serves it instead."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = app.state.container is None
        if owned:  # importing this module must not open the database: only a running server does
            app.state.container = build_container()
        if app.state.container.settings.preload_pipeline:
            app.state.container.recognition.warmup()  # pay the model loading time at startup, not on a request
        yield
        if owned:
            app.state.container.close()

    app = FastAPI(title="VN-ALPR API", version="0.2.0", lifespan=lifespan)
    app.state.container = container

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(recognition.router)
    app.include_router(gate.router)
    app.include_router(parking.router)
    if web_dir and Path(web_dir).is_dir():
        # registered last, so every API route above wins over the static files
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


app = create_app(web_dir=os.getenv("ALPR_WEB_DIR"))
