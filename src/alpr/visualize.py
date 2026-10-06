from __future__ import annotations

from collections.abc import Iterable

import cv2
import numpy as np

from alpr.types import PlateResult


def draw_results(img: np.ndarray, results: Iterable[PlateResult], fps: float | None = None) -> np.ndarray:
    out = img.copy()
    for r in results:
        x1, y1, x2, y2 = r.box
        color = (0, 200, 0) if r.valid else (0, 165, 255)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = r.display or "?"
        if r.track_id is not None:
            label = f"#{r.track_id} {label}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        ty = max(th + 6, y1)
        cv2.rectangle(out, (x1, ty - th - 6), (x1 + tw + 6, ty), color, -1)
        cv2.putText(out, label, (x1 + 3, ty - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
    if fps is not None:
        cv2.putText(out, f"{fps:.1f} FPS", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2, cv2.LINE_AA)
    return out
