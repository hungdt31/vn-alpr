"""What services need from the outside world, as small interfaces (implemented in infra/, faked in tests)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import numpy as np

from alpr.types import PlateResult


class Clock(Protocol):
    def now(self) -> datetime: ...


class PlateReader(Protocol):
    """The recognition pipeline (alpr.pipeline.ALPRPipeline) or a fake."""

    def process_image(self, img: np.ndarray) -> list[PlateResult]: ...
