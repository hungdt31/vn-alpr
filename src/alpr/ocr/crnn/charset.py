from __future__ import annotations

import numpy as np

DEFAULT_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Charset:
    """CTC label mapping; index 0 is the blank."""

    BLANK = 0

    def __init__(self, chars: str = DEFAULT_CHARS):
        self.chars = chars
        self._index = {c: i + 1 for i, c in enumerate(chars)}

    @property
    def num_classes(self) -> int:
        return len(self.chars) + 1

    def encode(self, text: str) -> list[int]:
        return [self._index[c] for c in text if c in self._index]

    def decode_greedy(self, probs: np.ndarray) -> list[tuple[str, float]]:
        """probs: [T, B, K] softmax probabilities -> (text, mean max-prob of emitted chars) per item."""
        best = probs.argmax(axis=2)  # [T, B]
        best_p = probs.max(axis=2)
        out = []
        for b in range(best.shape[1]):
            chars, confs = [], []
            prev = self.BLANK
            for t in range(best.shape[0]):
                k = int(best[t, b])
                if k != self.BLANK and k != prev:
                    chars.append(self.chars[k - 1])
                    confs.append(float(best_p[t, b]))
                prev = k
            out.append(("".join(chars), float(np.mean(confs)) if confs else 0.0))
        return out
