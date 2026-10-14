"""Plate recognition on an uploaded image."""

from __future__ import annotations

import time
from collections.abc import Callable

import cv2
import numpy as np

from alpr.types import PlateResult
from app.core.errors import BadImage
from app.services.ports import PlateReader


class RecognitionService:
    def __init__(self, reader: PlateReader | Callable[[], PlateReader]):
        """reader: the pipeline, or a factory called on first use (loading the models takes a few seconds)."""
        self._reader = reader if hasattr(reader, "process_image") else None
        self._factory = None if self._reader else reader

    @property
    def reader(self) -> PlateReader:
        if self._reader is None:
            self._reader = self._factory()
        return self._reader

    @staticmethod
    def decode(data: bytes) -> np.ndarray:
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise BadImage("Cannot decode image")
        return img

    @staticmethod
    def encode_jpeg(img: np.ndarray, quality: int = 90) -> bytes:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise BadImage("Cannot encode image")
        return buf.tobytes()

    def warmup(self) -> None:
        """Load the models and run one blank image, so the first real request is as fast as the next ones."""
        self.reader.process_image(np.zeros((480, 640, 3), np.uint8))

    def read(self, img: np.ndarray) -> tuple[list[PlateResult], float]:
        """Plates found in the image and the time it took, in ms."""
        t0 = time.perf_counter()
        plates = self.reader.process_image(img)
        return plates, round((time.perf_counter() - t0) * 1000, 1)
