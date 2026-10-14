"""Plates typed by people, and the exit check (plate on the ticket vs plate read at the exit)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from alpr.metrics import levenshtein
from alpr.postprocess.plate_format import PlateText, normalize, parse_plate
from app.domain.models import MatchStatus


def parse_plate_input(text: str) -> PlateText:
    """A plate typed by a person. Lines of a 2-line plate may be separated by "/" or a space, which is also how
    the pipeline displays them ("54-L1 9999"). The plate identity (normalized text) is the same either way."""
    return parse_plate([t for t in re.split(r"[/\s]+", text) if t])


@dataclass
class MatchPolicy:
    """configs/parking.yaml, `matching`."""

    max_suspect_distance: int = 1
    suspect_below_conf: float = 0.95


@dataclass
class PlateMatch:
    status: MatchStatus
    read: str  # normalized plate read at the exit ("" if none)
    distance: int  # edit distance to the ticket's plate
    reason: str  # human readable, shown to the guard


def match_exit_plate(expected: str, reads: list[tuple[str, float]], policy: MatchPolicy) -> PlateMatch:
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
    if distance <= policy.max_suspect_distance and conf < policy.suspect_below_conf:
        return PlateMatch("suspect", read, distance, f"Lệch {distance} ký tự, độ tin cậy thấp: có thể model đọc sai")
    return PlateMatch("mismatch", read, distance, "Biển số KHÔNG khớp với thẻ")
