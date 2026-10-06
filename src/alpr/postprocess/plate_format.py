"""Vietnamese license plate normalization, validation and position-based correction.

Normalized form drops separators: "51G-123.45" -> "51G12345".

Plate = province (2 digits) + series + number (4-5 digits). Series templates:
    DDL    51G-123.45      car, 1 letter
    DDLL   30LD-123.45     car, 2 letters
    DDLD   59-X1 123.45    motorbike, letter + digit
    DDLLD  29-MD1 123.45   electric motorbike (MĐ1)
(D = digit, L = letter.)
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from alpr.types import PlateText

# Letters used in VN plate series (no I, J, O, Q, W).
VALID_LETTERS = frozenset("ABCDEFGHKLMNPRSTUVXYZ")

# OCR confusions: what a character most likely is when the position requires a digit / a letter.
TO_DIGIT = {
    "O": "0", "Q": "0", "D": "0", "U": "0",
    "I": "1", "L": "1", "T": "1", "J": "1",
    "Z": "2", "A": "4", "S": "5", "G": "6", "B": "8",
}
TO_LETTER = {
    "0": "D", "O": "D", "Q": "D",
    "1": "T", "I": "T", "J": "U",
    "2": "Z", "4": "A", "5": "S", "6": "G", "8": "B", "W": "V",
}

# Order breaks ties: 1-line plates are cars (30LD-...), a 4-char first line of a 2-line plate is
# usually a motorbike series (59-X1).
PREFIX_TEMPLATES = ("DDL", "DDLL", "DDLD", "DDLLD")
PREFIX_TEMPLATES_TWO_LINE = ("DDL", "DDLD", "DDLL", "DDLLD")
NUMBER_LENGTHS = (5, 4)

PLATE_RE = re.compile(r"^\d{2}[A-Z]{1,2}\d?\d{4,5}$")


def normalize(text: str) -> str:
    """Uppercase, map Đ -> D, keep only A-Z and 0-9."""
    text = text.upper().replace("Đ", "D")
    return re.sub(r"[^A-Z0-9]", "", text)


def _coerce(s: str, template: str, allow_fix: bool) -> tuple[str, int] | None:
    out = []
    fixes = 0
    for ch, kind in zip(s, template):
        if kind == "D":
            if ch.isdigit():
                out.append(ch)
            elif allow_fix and ch in TO_DIGIT:
                out.append(TO_DIGIT[ch])
                fixes += 1
            else:
                return None
        else:
            if ch in VALID_LETTERS:
                out.append(ch)
            elif allow_fix and ch in TO_LETTER:
                out.append(TO_LETTER[ch])
                fixes += 1
            else:
                return None
    return "".join(out), fixes


def _best_match(
    s: str, prefix_len: int | None, allow_fix: bool, two_line: bool = False
) -> tuple[str, int, int] | None:
    """Return (text, n_fixes, prefix_len) of the template needing the fewest fixes."""
    best = None
    for prefix in PREFIX_TEMPLATES_TWO_LINE if two_line else PREFIX_TEMPLATES:
        if prefix_len is not None and len(prefix) != prefix_len:
            continue
        n_digits = len(s) - len(prefix)
        if n_digits not in NUMBER_LENGTHS:
            continue
        coerced = _coerce(s, prefix + "D" * n_digits, allow_fix)
        if coerced is None:
            continue
        text, fixes = coerced
        if prefix == "DDLLD" and text[2:4] != "MD":  # 3-char series only exists for electric bikes (MĐ1)
            continue
        if best is None or fixes < best[1]:  # ties keep the earlier (more common) template
            best = (text, fixes, len(prefix))
    return best


def format_display(text: str, prefix_len: int, two_line: bool = False) -> str:
    province, series, number = text[:2], text[2:prefix_len], text[prefix_len:]
    num = f"{number[:3]}.{number[3:]}" if len(number) == 5 else number
    if two_line:
        head = f"{province}-{series}" if any(c.isdigit() for c in series) else f"{province}{series}"
        return f"{head} {num}"
    return f"{province}{series}-{num}"


def parse_plate(lines: Sequence[str] | str, fix: bool = True) -> PlateText:
    """Turn raw OCR line(s) into a normalized, validated plate.

    For 2-line plates pass the lines separately: the first line length tells where the series ends.
    With fix=False only exact template matches are accepted (used for ablation).
    """
    if isinstance(lines, str):
        lines = [lines]
    parts = [p for p in (normalize(line) for line in lines) if p]
    raw = "".join(parts)
    two_line = len(parts) >= 2

    best = _best_match(raw, len(parts[0]) if two_line else None, fix, two_line)
    if two_line:
        # the line split may be off by a character: trust the joined string if it needs fewer fixes
        free = _best_match(raw, None, fix, two_line)
        if free is not None and (best is None or free[1] < best[1]):
            best = free
    if best is None:
        return PlateText(text=raw, display=raw, valid=False)

    text, fixes, prefix_len = best
    return PlateText(text=text, display=format_display(text, prefix_len, two_line), valid=True, n_fixes=fixes)


def is_valid_plate(text: str) -> bool:
    return bool(PLATE_RE.match(normalize(text)))
