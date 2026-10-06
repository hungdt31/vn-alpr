"""PaddleOCR baseline recognizer (recognition only: plate lines are already cropped).

Supports both PaddleOCR 2.x (`PaddleOCR.ocr(det=False)`) and 3.x (`TextRecognition`).
"""

from __future__ import annotations

import numpy as np


class PaddleRecognizer:
    def __init__(self, lang: str = "en"):
        try:
            import paddleocr
        except ImportError as e:
            raise ImportError("PaddleOCR not installed: pip install -r requirements-paddle.txt") from e

        major = int(str(getattr(paddleocr, "__version__", "2")).split(".")[0])
        self._v3 = major >= 3
        if self._v3:
            self._model = paddleocr.TextRecognition()
        else:
            self._model = paddleocr.PaddleOCR(lang=lang, use_angle_cls=False, show_log=False)

    def _read_one(self, img: np.ndarray) -> tuple[str, float]:
        if self._v3:
            res = self._model.predict(input=img)
            if not res:
                return "", 0.0
            r = res[0]
            return str(r["rec_text"]), float(r["rec_score"])
        res = self._model.ocr(img, det=False, cls=False)
        if not res or not res[0]:
            return "", 0.0
        text, score = res[0][0]
        return str(text), float(score)

    def recognize(self, images: list[np.ndarray]) -> list[tuple[str, float]]:
        return [self._read_one(img) for img in images]
