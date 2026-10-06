"""YOLO plate detector (Ultralytics). Accepts .pt, .onnx or TensorRT .engine weights."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from alpr.types import Detection


class PlateDetector:
    def __init__(
        self,
        weights: str | Path,
        conf: float = 0.4,
        iou: float = 0.5,
        imgsz: int = 640,
        device: str | None = None,
        tracker: str = "bytetrack.yaml",
    ):
        from ultralytics import YOLO

        if not Path(weights).exists():
            raise FileNotFoundError(f"Detector weights not found: {weights} (train with scripts/train_detector.py)")
        self.model = YOLO(str(weights), task="detect")
        self.kwargs = dict(conf=conf, iou=iou, imgsz=imgsz, verbose=False)
        if device is not None:
            self.kwargs["device"] = device
        self.tracker = tracker

    @staticmethod
    def _to_detections(result) -> list[Detection]:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy().round().astype(int)
        confs = boxes.conf.cpu().numpy()
        ids = boxes.id.cpu().numpy().astype(int).tolist() if boxes.id is not None else [None] * len(xyxy)
        return [Detection(tuple(int(v) for v in b), float(c), tid) for b, c, tid in zip(xyxy, confs, ids)]

    def detect(self, img: np.ndarray) -> list[Detection]:
        return self._to_detections(self.model.predict(img, **self.kwargs)[0])

    def track(self, frame: np.ndarray) -> list[Detection]:
        """Detection + ByteTrack ids; state persists across calls until reset_tracker()."""
        return self._to_detections(self.model.track(frame, persist=True, tracker=self.tracker, **self.kwargs)[0])

    def reset_tracker(self) -> None:
        predictor = getattr(self.model, "predictor", None)
        for t in getattr(predictor, "trackers", None) or []:
            t.reset()
