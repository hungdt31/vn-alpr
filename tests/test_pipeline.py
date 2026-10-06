"""Pipeline logic with fake detector/recognizer (no model weights needed)."""

import numpy as np
import pytest

from alpr.config import PipelineConfig, load_config
from alpr.pipeline import ALPRPipeline
from alpr.synth import render_plate
from alpr.types import Detection


class FakeDetector:
    def __init__(self, boxes, track_ids=None):
        self.boxes = boxes
        self.track_ids = track_ids or [None] * len(boxes)
        self.reset_called = False

    def detect(self, img):
        return [Detection(b, 0.9) for b in self.boxes]

    def track(self, frame):
        return [Detection(b, 0.9, t) for b, t in zip(self.boxes, self.track_ids)]

    def reset_tracker(self):
        self.reset_called = True


class FakeRecognizer:
    """Returns queued readings; records how many line images it received."""

    def __init__(self, readings):
        self.readings = list(readings)
        self.calls = []

    def recognize(self, images):
        self.calls.append(len(images))
        return [self.readings.pop(0) for _ in images]


def scene_with(plate: np.ndarray):
    img = np.full((480, 640, 3), 90, np.uint8)
    h, w = plate.shape[:2]
    img[100 : 100 + h, 50 : 50 + w] = plate
    return img, (50, 100, 50 + w, 100 + h)


def test_one_line_plate_with_fix():
    img, box = scene_with(render_plate(["51G-123.45"]))
    rec = FakeRecognizer([("S1G-123.45", 0.8)])
    results = ALPRPipeline(FakeDetector([box]), rec).process_image(img)
    assert rec.calls == [1]
    r = results[0]
    assert r.valid and r.text == "51G12345" and r.display == "51G-123.45" and not r.two_line


def test_two_line_plate_is_split():
    img, box = scene_with(render_plate(["59-X1", "123.45"]))
    rec = FakeRecognizer([("59-X1", 0.9), ("123.45", 0.7)])
    r = ALPRPipeline(FakeDetector([box]), rec).process_image(img)[0]
    assert rec.calls == [2]
    assert r.two_line and r.display == "59-X1 123.45"
    assert r.ocr_conf == pytest.approx(0.8)


def test_postprocess_disabled_keeps_raw_text():
    img, box = scene_with(render_plate(["51G-123.45"]))
    cfg = PipelineConfig()
    cfg.postprocess.enabled = False
    r = ALPRPipeline(FakeDetector([box]), FakeRecognizer([("S1G-123.45", 0.8)]), cfg).process_image(img)[0]
    assert not r.valid and r.text == "S1G12345"


def test_video_voting_confirms_and_skips_ocr_after():
    img, box = scene_with(render_plate(["51G-123.45"]))
    cfg = PipelineConfig()
    cfg.tracking.min_hits = 2
    rec = FakeRecognizer([("51G-123.45", 0.9)] * 2)
    det = FakeDetector([box], track_ids=[5])
    p = ALPRPipeline(det, rec, cfg)

    _, ev0 = p.process_frame(img, 0)
    _, ev1 = p.process_frame(img, 1)
    results, ev2 = p.process_frame(img, 2)
    assert ev0 == [] and len(ev1) == 1 and ev2 == []
    assert ev1[0].text == "51G12345"
    assert len(rec.calls) == 2  # third frame reused the confirmed reading
    assert results[0].display == "51G-123.45"

    assert p.finish_video(3) == []
    assert det.reset_called


def test_load_config_file(tmp_path):
    cfg = load_config("configs/pipeline.yaml")
    assert cfg.ocr.engine in ("crnn", "paddle")
    bad = tmp_path / "bad.yaml"
    bad.write_text("detector:\n  weigths: x\n")
    with pytest.raises(ValueError):
        load_config(bad)
