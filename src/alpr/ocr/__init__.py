from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import numpy as np

if TYPE_CHECKING:
    from alpr.config import OCRConfig


class Recognizer(Protocol):
    def recognize(self, images: list[np.ndarray]) -> list[tuple[str, float]]:
        """Read one text line per image, returning (text, confidence in [0, 1])."""
        ...


def build_recognizer(cfg: OCRConfig) -> Recognizer:
    if cfg.engine == "crnn":
        from alpr.ocr.crnn.recognizer import CRNNRecognizer

        return CRNNRecognizer(cfg.crnn_weights, device=cfg.device)
    if cfg.engine == "paddle":
        from alpr.ocr.paddle import PaddleRecognizer

        return PaddleRecognizer()
    raise ValueError(f"Unknown OCR engine: {cfg.engine!r} (expected 'crnn' or 'paddle')")
