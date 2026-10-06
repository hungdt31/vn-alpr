"""Multi-frame voting: one stable plate reading per tracked vehicle."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from alpr.types import PlateEvent


@dataclass
class _Track:
    last_seen: int
    scores: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    displays: dict[str, str] = field(default_factory=dict)
    hits: int = 0
    emitted: bool = False


class TrackVoter:
    """Accumulates confidence-weighted OCR readings per track id.

    A track is confirmed (emitted once) when it has `min_hits` valid readings and the top reading
    holds at least `min_agreement` of the total weight. Tracks unseen for `max_age` frames are
    dropped; if they were never confirmed but have enough readings, the best guess is emitted.
    """

    def __init__(self, min_hits: int = 3, min_agreement: float = 0.6, max_age: int = 30):
        self.min_hits = min_hits
        self.min_agreement = min_agreement
        self.max_age = max_age
        self._tracks: dict[int, _Track] = {}

    def reset(self) -> None:
        self._tracks.clear()

    def is_emitted(self, track_id: int) -> bool:
        t = self._tracks.get(track_id)
        return t is not None and t.emitted

    def touch(self, track_id: int, frame_idx: int) -> None:
        t = self._tracks.get(track_id)
        if t is not None:
            t.last_seen = frame_idx

    def best(self, track_id: int) -> tuple[str, str, float] | None:
        """(text, display, agreement) of the leading reading."""
        t = self._tracks.get(track_id)
        if t is None or not t.scores:
            return None
        text = max(t.scores, key=t.scores.__getitem__)
        return text, t.displays[text], t.scores[text] / sum(t.scores.values())

    def update(
        self, track_id: int, text: str, display: str, conf: float, valid: bool, frame_idx: int
    ) -> PlateEvent | None:
        t = self._tracks.setdefault(track_id, _Track(last_seen=frame_idx))
        t.last_seen = frame_idx
        if not valid or not text:
            return None
        t.scores[text] += max(conf, 1e-3)
        t.displays[text] = display
        t.hits += 1
        if t.emitted or t.hits < self.min_hits:
            return None
        best_text, best_display, agreement = self.best(track_id)
        if agreement < self.min_agreement:
            return None
        t.emitted = True
        return PlateEvent(track_id, best_text, best_display, agreement, t.hits, frame_idx)

    def flush(self, frame_idx: int, force: bool = False) -> list[PlateEvent]:
        """Drop stale tracks (all tracks if force=True), emitting unconfirmed ones with enough hits."""
        events = []
        for tid in list(self._tracks):
            t = self._tracks[tid]
            if not force and frame_idx - t.last_seen <= self.max_age:
                continue
            if not t.emitted and t.hits >= self.min_hits:
                text, display, agreement = self.best(tid)
                events.append(PlateEvent(tid, text, display, agreement, t.hits, frame_idx))
            del self._tracks[tid]
        return events
