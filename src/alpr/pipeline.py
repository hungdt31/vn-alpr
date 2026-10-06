"""End-to-end ALPR: detect -> crop -> deskew -> split lines -> OCR -> VN post-processing (-> track & vote)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from alpr.config import PipelineConfig, load_config
from alpr.ocr import Recognizer, build_recognizer
from alpr.postprocess.plate_format import normalize, parse_plate
from alpr.preprocess import crop_box, deskew, is_two_line, split_lines
from alpr.tracking.voter import TrackVoter
from alpr.types import Detection, PlateEvent, PlateResult, PlateText


class Detector(Protocol):
    def detect(self, img: np.ndarray) -> list[Detection]: ...
    def track(self, frame: np.ndarray) -> list[Detection]: ...


class ALPRPipeline:
    def __init__(self, detector: Detector, recognizer: Recognizer, config: PipelineConfig | None = None):
        self.detector = detector
        self.recognizer = recognizer
        self.cfg = config or PipelineConfig()
        t = self.cfg.tracking
        self.voter = TrackVoter(t.min_hits, t.min_agreement, t.max_age)

    @classmethod
    def from_config(cls, config: PipelineConfig | str | Path) -> ALPRPipeline:
        cfg = config if isinstance(config, PipelineConfig) else load_config(config)
        from alpr.detection.detector import PlateDetector

        d = cfg.detector
        detector = PlateDetector(d.weights, d.conf, d.iou, d.imgsz, d.device, cfg.tracking.tracker)
        return cls(detector, build_recognizer(cfg.ocr), cfg)

    # ---- single plate -------------------------------------------------------------------------
    def read_plate(self, crop: np.ndarray) -> tuple[PlateText, float, bool, list[str]]:
        """OCR an already-cropped plate. Returns (plate, ocr_conf, two_line, raw_lines)."""
        pp = self.cfg.postprocess
        if crop.size == 0:
            return PlateText("", "", False), 0.0, False, []
        if pp.deskew:
            crop = deskew(crop)
        two_line = is_two_line(crop, pp.two_line_ratio)
        lines = split_lines(crop) if two_line else [crop]
        reads = self.recognizer.recognize(lines)
        raw = [text for text, _ in reads]
        conf = float(np.mean([c for _, c in reads])) if reads else 0.0
        if pp.enabled:
            plate = parse_plate(raw)
        else:  # ablation: raw OCR output, only a strict format check
            plate = parse_plate(raw, fix=False)
            if not plate.valid:
                text = normalize("".join(raw))
                plate = PlateText(text, text, False)
        return plate, conf, two_line, raw

    def _result(self, img: np.ndarray, det: Detection) -> PlateResult:
        crop = crop_box(img, det.box, self.cfg.postprocess.crop_pad)
        plate, conf, two_line, raw = self.read_plate(crop)
        return PlateResult(
            box=det.box, det_conf=det.conf, text=plate.text, display=plate.display, ocr_conf=conf,
            valid=plate.valid, two_line=two_line, raw_lines=raw, track_id=det.track_id,
        )

    # ---- images -------------------------------------------------------------------------------
    def process_image(self, img: np.ndarray) -> list[PlateResult]:
        return [self._result(img, d) for d in self.detector.detect(img)]

    # ---- video --------------------------------------------------------------------------------
    def process_frame(self, frame: np.ndarray, frame_idx: int) -> tuple[list[PlateResult], list[PlateEvent]]:
        """Track plates and vote across frames. Confirmed tracks skip OCR to save compute."""
        results: list[PlateResult] = []
        events: list[PlateEvent] = []
        for det in self.detector.track(frame):
            tid = det.track_id
            if tid is not None and self.voter.is_emitted(tid):
                self.voter.touch(tid, frame_idx)
                text, display, agreement = self.voter.best(tid)
                results.append(PlateResult(det.box, det.conf, text, display, agreement, True, False, [], tid))
                continue
            r = self._result(frame, det)
            results.append(r)
            if tid is not None:
                ev = self.voter.update(tid, r.text, r.display, r.ocr_conf, r.valid, frame_idx)
                if ev is not None:
                    events.append(ev)
        events.extend(self.voter.flush(frame_idx))
        return results, events

    def finish_video(self, frame_idx: int) -> list[PlateEvent]:
        """Emit pending tracks and reset tracking state before the next video."""
        events = self.voter.flush(frame_idx, force=True)
        self.voter.reset()
        reset = getattr(self.detector, "reset_tracker", None)
        if reset is not None:
            reset()
        return events
