from __future__ import annotations

from collections.abc import Sequence

from alpr.postprocess.plate_format import normalize


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def char_accuracy(preds: Sequence[str], gts: Sequence[str]) -> float:
    """1 - CER, computed on normalized strings."""
    total = sum(len(normalize(g)) for g in gts)
    if total == 0:
        return 0.0
    errors = sum(levenshtein(normalize(p), normalize(g)) for p, g in zip(preds, gts))
    return max(0.0, 1.0 - errors / total)


def plate_accuracy(preds: Sequence[str], gts: Sequence[str]) -> float:
    """Exact match on normalized strings."""
    if not gts:
        return 0.0
    return sum(normalize(p) == normalize(g) for p, g in zip(preds, gts)) / len(gts)
