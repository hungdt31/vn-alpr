"""Pure business rules: parking fee and the exit plate check."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

from alpr.metrics import levenshtein
from alpr.postprocess.plate_format import PlateText, normalize, parse_plate
from app.parking.config import FeeConfig, MatchConfig


def parse_plate_input(text: str) -> PlateText:
    """A plate typed by a person. Lines of a 2-line plate may be separated by "/" or a space, which is also how
    the pipeline displays them ("54-L1 9999"). The plate identity (normalized text) is the same either way."""
    return parse_plate([t for t in re.split(r"[/\s]+", text) if t])


def parking_fee(fee: FeeConfig, entry: datetime, exit_: datetime, lost_card: bool = False) -> int:
    """base for the first base_hours, then per_hour for every started hour after; never below base."""
    hours = max(0.0, (exit_ - entry).total_seconds() / 3600)
    extra_hours = max(0, math.ceil(hours - fee.base_hours - 1e-9))
    return fee.base + extra_hours * fee.per_hour + (fee.lost_card if lost_card else 0)


@dataclass
class PlateMatch:
    status: str  # "ok" | "suspect" | "mismatch"
    read: str  # normalized plate read at the exit ("" if none)
    distance: int  # edit distance to the ticket's plate
    reason: str  # human readable, shown to the guard


def match_exit_plate(expected: str, reads: list[tuple[str, float]], cfg: MatchConfig) -> PlateMatch:
    """Compare the plates read at the exit with the plate stored on the ticket.

    reads: (text, ocr_conf) for every plate found in the exit image; the closest one is used.
    A one-character difference read with low confidence is "suspect" (likely an OCR error) rather than a
    hard "mismatch", so the guard can tell a misread from a different vehicle.
    """
    expected = normalize(expected)
    candidates = [(normalize(t), c) for t, c in reads if normalize(t)]
    if not candidates:
        return PlateMatch("suspect", "", len(expected), "Không đọc được biển số ở cổng ra")
    read, conf = min(candidates, key=lambda rc: (levenshtein(rc[0], expected), -rc[1]))
    distance = levenshtein(read, expected)
    if distance == 0:
        return PlateMatch("ok", read, 0, "Biển số khớp với thẻ")
    if distance <= cfg.max_suspect_distance and conf < cfg.suspect_below_conf:
        return PlateMatch("suspect", read, distance, f"Lệch {distance} ký tự, độ tin cậy thấp: có thể model đọc sai")
    return PlateMatch("mismatch", read, distance, "Biển số KHÔNG khớp với thẻ")
