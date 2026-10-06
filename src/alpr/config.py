from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


@dataclass
class DetectorConfig:
    weights: str = "models/detector/best.pt"
    conf: float = 0.4
    iou: float = 0.5
    imgsz: int = 640
    device: str | None = None


@dataclass
class OCRConfig:
    engine: str = "crnn"  # crnn | paddle
    crnn_weights: str = "models/crnn/best.pt"
    device: str = "cpu"


@dataclass
class PostprocessConfig:
    enabled: bool = True
    deskew: bool = True
    two_line_ratio: float = 2.5
    crop_pad: float = 0.05


@dataclass
class TrackingConfig:
    tracker: str = "bytetrack.yaml"
    min_hits: int = 3
    min_agreement: float = 0.6
    max_age: int = 30


@dataclass
class PipelineConfig:
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    postprocess: PostprocessConfig = field(default_factory=PostprocessConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)


def _build(cls, data: dict | None):
    data = data or {}
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Unknown keys for {cls.__name__}: {sorted(unknown)}")
    return cls(**data)


def load_config(path: str | Path) -> PipelineConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return PipelineConfig(
        detector=_build(DetectorConfig, raw.get("detector")),
        ocr=_build(OCRConfig, raw.get("ocr")),
        postprocess=_build(PostprocessConfig, raw.get("postprocess")),
        tracking=_build(TrackingConfig, raw.get("tracking")),
    )
