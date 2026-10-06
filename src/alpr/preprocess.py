"""Plate crop preparation: cropping, deskew, 1-line / 2-line detection and line splitting."""

from __future__ import annotations

import cv2
import numpy as np

from alpr.types import Box


def to_gray(img: np.ndarray) -> np.ndarray:
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def binarize_text(img: np.ndarray) -> np.ndarray:
    """Otsu binarization with characters as foreground (255), regardless of plate polarity."""
    gray = to_gray(img)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if binary.mean() > 127:  # light text on dark plate: background became foreground
        binary = 255 - binary
    return binary


def crop_box(img: np.ndarray, box: Box, pad: float = 0.05) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    px, py = int((x2 - x1) * pad), int((y2 - y1) * pad)
    x1, y1 = max(0, x1 - px), max(0, y1 - py)
    x2, y2 = min(w, x2 + px), min(h, y2 + py)
    return img[y1:y2, x1:x2].copy()


def estimate_skew(img: np.ndarray) -> float:
    """Angle (degrees) of the text block, positive = counter-clockwise rotation needed to level it."""
    binary = binarize_text(img)
    # ignore the plate frame touching the crop border
    h, w = binary.shape
    mh, mw = max(1, h // 10), max(1, w // 20)
    inner = np.zeros_like(binary)
    inner[mh : h - mh, mw : w - mw] = binary[mh : h - mh, mw : w - mw]
    coords = cv2.findNonZero(inner)
    if coords is None or len(coords) < 20:
        return 0.0
    # minAreaRect's angle convention changed across OpenCV versions, so measure the long edge directly
    pts = cv2.boxPoints(cv2.minAreaRect(coords))
    edges = [pts[(i + 1) % 4] - pts[i] for i in range(2)]
    dx, dy = max(edges, key=lambda e: float(np.hypot(*e)))
    angle = float(np.degrees(np.arctan2(dy, dx)))  # image y points down: this is the CCW correction
    if angle > 90:
        angle -= 180
    elif angle <= -90:
        angle += 180
    return angle


def deskew(img: np.ndarray, max_angle: float = 15.0, min_angle: float = 1.0) -> np.ndarray:
    angle = estimate_skew(img)
    if not (min_angle <= abs(angle) <= max_angle):
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def is_two_line(img: np.ndarray, ratio_threshold: float = 2.5) -> bool:
    """1-line VN plates are ~4.7:1, 2-line plates ~1.4:1."""
    h, w = img.shape[:2]
    return h > 0 and w / h < ratio_threshold


def find_split_row(img: np.ndarray) -> int:
    """Row between the two text lines: the emptiest row in the middle band of the plate."""
    binary = binarize_text(img)
    h = binary.shape[0]
    lo, hi = int(h * 0.3), int(h * 0.7)
    if hi - lo < 2:
        return h // 2
    profile = binary[lo:hi].astype(np.float32).sum(axis=1)
    profile = np.convolve(profile, np.ones(3) / 3, mode="same")
    candidates = np.flatnonzero(profile <= profile.min() + 1e-6)
    return lo + int(candidates[len(candidates) // 2])  # centre of the gap


def split_lines(img: np.ndarray) -> list[np.ndarray]:
    y = find_split_row(img)
    return [img[:y], img[y:]]
