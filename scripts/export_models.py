"""Export trained models for faster inference.

    python scripts/export_models.py --detector models/detector/best.pt --crnn models/crnn/best.pt
    python scripts/export_models.py --detector models/detector/best.pt --format engine --half   # TensorRT (GPU)
"""

import argparse

import _bootstrap  # noqa: F401

from alpr.export import export_crnn, export_detector


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector")
    ap.add_argument("--crnn")
    ap.add_argument("--format", default="onnx", choices=["onnx", "engine"])
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--half", action="store_true", help="FP16 (TensorRT)")
    args = ap.parse_args()

    if args.detector:
        print("detector ->", export_detector(args.detector, args.format, args.imgsz, args.half))
    if args.crnn:
        print("crnn     ->", export_crnn(args.crnn))
    if not (args.detector or args.crnn):
        ap.error("pass --detector and/or --crnn")


if __name__ == "__main__":
    main()
