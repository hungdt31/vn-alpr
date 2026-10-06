"""Synthetic VN plate rendering, used to pre-train the CRNN and in tests.

Uses OpenCV Hershey fonts so it runs anywhere without font files. The glyphs differ from the
real VN plate font, so synthetic data is for pre-training only - always fine-tune on real crops.
"""

from __future__ import annotations

import cv2
import numpy as np

SERIES_LETTERS = "ABCDEFGHKLMNPSTUVXYZ"


def random_plate(rng: np.random.Generator, two_line: bool | None = None) -> list[str]:
    """Random plate as display lines, e.g. ["51G-123.45"] or ["59-X1", "123.45"]."""
    if two_line is None:
        two_line = bool(rng.random() < 0.5)
    province = f"{rng.integers(11, 100):02d}"
    n_digits = 5 if rng.random() < 0.8 else 4
    digits = "".join(str(d) for d in rng.integers(0, 10, n_digits))
    number = f"{digits[:3]}.{digits[3:]}" if n_digits == 5 else digits
    letter = SERIES_LETTERS[rng.integers(len(SERIES_LETTERS))]

    if not two_line:
        series = letter + (SERIES_LETTERS[rng.integers(len(SERIES_LETTERS))] if rng.random() < 0.15 else "")
        return [f"{province}{series}-{number}"]
    if rng.random() < 0.3:  # car, 2 lines
        return [f"{province}{letter}", number]
    return [f"{province}-{letter}{rng.integers(1, 10)}", number]  # motorbike


def _fit_scale(text: str, font: int, thickness: int, max_w: float, max_h: float) -> float:
    (tw, th), _ = cv2.getTextSize(text, font, 1.0, thickness)
    return min(max_w / tw, max_h / th)


def render_plate(
    lines: list[str],
    rng: np.random.Generator | None = None,
    height: int | None = None,
) -> np.ndarray:
    """Render a clean plate (BGR). 1-line plates are 470x110, 2-line 280x200 (before scaling)."""
    rng = rng or np.random.default_rng()
    two_line = len(lines) >= 2
    w, h = (280, 200) if two_line else (470, 110)
    bg = int(rng.integers(200, 256))
    fg = int(rng.integers(0, 60))
    img = np.full((h, w, 3), bg, np.uint8)
    cv2.rectangle(img, (3, 3), (w - 4, h - 4), (fg, fg, fg), 4)

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = int(rng.integers(5, 9))
    line_h = h * (0.36 if two_line else 0.62)
    for i, text in enumerate(lines):
        scale = _fit_scale(text, font, thickness, w * 0.86, line_h)
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        x = (w - tw) // 2
        if two_line:
            y = int(h * (0.42 if i == 0 else 0.86))
        else:
            y = (h + th) // 2
        cv2.putText(img, text, (x, y), font, scale, (fg, fg, fg), thickness, cv2.LINE_AA)

    if height is not None:
        img = cv2.resize(img, (int(w * height / h), height), interpolation=cv2.INTER_AREA)
    return img


def augment(img: np.ndarray, rng: np.random.Generator, strength: float = 1.0) -> np.ndarray:
    """Photometric + geometric noise mimicking real camera crops."""
    h, w = img.shape[:2]
    out = img.copy()

    # perspective jitter
    d = 0.06 * strength
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    jitter = rng.uniform(-d, d, (4, 2)) * np.float32([w, h])
    m = cv2.getPerspectiveTransform(src, (src + jitter).astype(np.float32))
    out = cv2.warpPerspective(out, m, (w, h), borderMode=cv2.BORDER_REPLICATE)

    # small rotation
    angle = rng.uniform(-5, 5) * strength
    rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    out = cv2.warpAffine(out, rot, (w, h), borderMode=cv2.BORDER_REPLICATE)

    # brightness / contrast
    alpha = rng.uniform(1 - 0.4 * strength, 1 + 0.3 * strength)
    beta = rng.uniform(-40, 40) * strength
    out = cv2.convertScaleAbs(out, alpha=alpha, beta=beta)

    # blur (defocus or motion)
    if rng.random() < 0.5 * strength:
        k = int(rng.choice([3, 5]))
        if rng.random() < 0.5:
            out = cv2.GaussianBlur(out, (k, k), 0)
        else:
            kernel = np.zeros((k, k), np.float32)
            kernel[k // 2, :] = 1.0 / k
            out = cv2.filter2D(out, -1, kernel)

    # sensor noise
    if rng.random() < 0.5 * strength:
        noise = rng.normal(0, 8 * strength, out.shape)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # down/up-scale to simulate low resolution
    if rng.random() < 0.3 * strength:
        f = rng.uniform(0.3, 0.7)
        small = cv2.resize(out, (max(8, int(w * f)), max(8, int(h * f))), interpolation=cv2.INTER_AREA)
        out = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    return out
