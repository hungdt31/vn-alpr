"""Measure detector-only and end-to-end FPS on a video or an image folder.

    python scripts/benchmark.py --source data/demo.mp4 --n 300
    python scripts/benchmark.py --source data/demo.mp4 --detector models/detector/best.onnx --crnn models/crnn/best.onnx
"""

import argparse
import time
from pathlib import Path

import _bootstrap  # noqa: F401
import cv2

from alpr.config import load_config
from alpr.pipeline import ALPRPipeline


def frames(source: str, n: int):
    p = Path(source)
    if p.is_dir():
        files = sorted(f for f in p.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png"})
        imgs = [cv2.imread(str(f)) for f in files[:n]]
        return [im for im in imgs if im is not None]
    cap = cv2.VideoCapture(source)
    out = []
    while len(out) < n:
        ok, frame = cap.read()
        if not ok:
            break
        out.append(frame)
    cap.release()
    return out


def timed(fn, items, warmup: int) -> float:
    for x in items[:warmup]:
        fn(x)
    t0 = time.perf_counter()
    for x in items:
        fn(x)
    return len(items) / (time.perf_counter() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--config", default="configs/pipeline.yaml")
    ap.add_argument("--detector", help="override detector weights (.pt/.onnx/.engine)")
    ap.add_argument("--crnn", help="override CRNN weights (.pt/.onnx)")
    ap.add_argument("--device", help="override detector device")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=10)
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.detector:
        cfg.detector.weights = args.detector
    if args.crnn:
        cfg.ocr.crnn_weights = args.crnn
    if args.device:
        cfg.detector.device = args.device
    pipeline = ALPRPipeline.from_config(cfg)

    items = frames(args.source, args.n)
    if not items:
        raise SystemExit(f"No frames read from {args.source}")
    h, w = items[0].shape[:2]
    det_fps = timed(pipeline.detector.detect, items, args.warmup)
    e2e_fps = timed(pipeline.process_image, items, args.warmup)
    print(f"frames: {len(items)} ({w}x{h})  detector: {cfg.detector.weights}  ocr: {cfg.ocr.engine}")
    print(f"detector only : {det_fps:6.1f} FPS")
    print(f"end-to-end    : {e2e_fps:6.1f} FPS  ({1000 / e2e_fps:.1f} ms/frame)")


if __name__ == "__main__":
    main()
