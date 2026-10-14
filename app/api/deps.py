"""FastAPI dependencies. Routers ask for a service; the services come from the app's Container."""

from __future__ import annotations

from fastapi import Depends, Request

from app.container import Container
from app.services.gate_log import GateLog
from app.services.parking import ParkingService
from app.services.recognition import RecognitionService


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_recognition(c: Container = Depends(get_container)) -> RecognitionService:
    return c.recognition


def get_gate_log(c: Container = Depends(get_container)) -> GateLog:
    return c.gate_log


def get_parking(c: Container = Depends(get_container)) -> ParkingService:
    return c.parking
