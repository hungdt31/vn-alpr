"""Composition root: the only place that knows how the layers are wired together.

    api/main.py         create_app() -> build_container()
    scripts/run_camera  open_gate_log()
    tests               build_container(settings, pipeline=FakePipeline(), clock=FixedClock())
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import Settings
from app.infra.clock import OffsetClock, SystemClock
from app.infra.db import Database
from app.infra.image_store import ImageStore
from app.infra.repositories.captures import CaptureRepository
from app.infra.repositories.cards import CardRepository
from app.infra.repositories.events import EventRepository
from app.infra.repositories.sessions import SessionRepository
from app.infra.repositories.slots import SlotRepository
from app.services.gate_log import GateLog
from app.services.parking import ParkingService
from app.services.ports import Clock, PlateReader
from app.services.recognition import RecognitionService


@dataclass
class Container:
    settings: Settings
    db: Database
    clock: Clock
    recognition: RecognitionService
    gate_log: GateLog
    parking: ParkingService

    def close(self) -> None:
        self.db.close()


def build_container(settings: Settings | None = None, pipeline: PlateReader | None = None,
                    clock: Clock | None = None) -> Container:
    """pipeline: None loads ALPRPipeline from settings on first use. clock: None is real time that the demo
    can fast-forward (OffsetClock)."""
    settings = settings or Settings.from_env()
    db = Database(settings.db)
    clock = clock or OffsetClock()

    def load_pipeline() -> PlateReader:
        from alpr.pipeline import ALPRPipeline  # heavy: ultralytics, torch

        return ALPRPipeline.from_config(settings.pipeline_config)

    gate_log = GateLog(db, EventRepository(db), clock, settings.gate_cooldown_s)
    parking = ParkingService(
        db, CardRepository(db), SlotRepository(db), SessionRepository(db), CaptureRepository(db),
        ImageStore(settings.parking.captures_dir), clock, settings.parking, gate_log=gate_log,
    )
    parking.setup()
    return Container(settings, db, clock, RecognitionService(pipeline or load_pipeline), gate_log, parking)


def open_gate_log(db_path: str, cooldown_s: float = 60.0) -> GateLog:
    """Just the gate log, for tools that run the pipeline themselves (run_camera.py)."""
    db = Database(db_path)
    return GateLog(db, EventRepository(db), SystemClock(), cooldown_s)
