from __future__ import annotations

from dataclasses import asdict, dataclass, field

Box = tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels


@dataclass
class Detection:
    box: Box
    conf: float
    track_id: int | None = None


@dataclass
class PlateText:
    text: str  # normalized, e.g. "51G12345"
    display: str  # human readable, e.g. "51G-123.45"
    valid: bool  # matches a VN plate template
    n_fixes: int = 0  # characters changed by position-based correction


@dataclass
class PlateResult:
    box: Box
    det_conf: float
    text: str
    display: str
    ocr_conf: float
    valid: bool
    two_line: bool
    raw_lines: list[str] = field(default_factory=list)
    track_id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlateEvent:
    """A plate confirmed over several video frames of the same track."""

    track_id: int
    text: str
    display: str
    confidence: float  # weighted agreement of the winning reading
    hits: int
    frame_idx: int

    def to_dict(self) -> dict:
        return asdict(self)
