"""Pre-label plate texts with an OCR engine, so a human only has to correct them.

For every YOLO box in the split detection dataset, crops the plate (same padding as make_ocr_crops.py),
reads it line by line and writes a draft row. Review the drafts with
`streamlit run scripts/review_texts.py`, which exports texts.csv / test_texts.csv.

    python scripts/draft_texts.py --ocr paddle --out data/drafts
    python scripts/draft_texts.py --limit test=300 --limit train=2000 --limit val=300

Output: <out>/drafts.csv  (split, image, plate_idx, crop, text, ocr_text, conf, valid, status)
        <out>/crops/<split>/<stem>_<idx>.jpg
"""

import argparse
import csv
import random
from pathlib import Path

import _bootstrap  # noqa: F401
import cv2
import numpy as np
from make_ocr_crops import yolo_boxes

from alpr.config import OCRConfig
from alpr.ocr import build_recognizer
from alpr.postprocess.plate_format import normalize, parse_plate
from alpr.preprocess import crop_box, is_two_line, split_lines

FIELDS = ["split", "image", "plate_idx", "crop", "text", "ocr_text", "conf", "valid", "status"]


def draft_text(lines: list[str]) -> tuple[str, bool]:
    """Best guess in texts.csv format: "51G-123.45" or "59-X1/123.45" (lines joined by "/")."""
    plate = parse_plate(lines)
    if not plate.valid:
        return "/".join(p for p in (normalize(t) for t in lines) if p), False
    if len([t for t in lines if normalize(t)]) >= 2:
        return plate.display.replace(" ", "/", 1), True  # 2-line display is "59-X1 123.45"
    return plate.display, True


def parse_limits(items: list[str]) -> dict[str, int]:
    limits = {}
    for item in items:
        split, _, n = item.partition("=")
        limits[split] = int(n)
    return limits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detection", default="data/processed/detection")
    ap.add_argument("--out", default="data/drafts")
    ap.add_argument("--ocr", choices=["paddle", "crnn"], default="paddle")
    ap.add_argument("--crnn-weights", default="models/crnn/best.pt")
    ap.add_argument("--pad", type=float, default=0.05)
    ap.add_argument("--two-line-ratio", type=float, default=2.5)
    ap.add_argument("--limit", action="append", default=[], metavar="SPLIT=N",
                    help="label at most N random images of SPLIT (repeatable), e.g. --limit test=300")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    recognizer = build_recognizer(OCRConfig(engine=args.ocr, crnn_weights=args.crnn_weights))
    limits = parse_limits(args.limit)
    det, out = Path(args.detection), Path(args.out)
    rows = []
    for split in ("train", "val", "test"):
        img_dir = det / "images" / split
        if not img_dir.exists():
            continue
        images = sorted(img_dir.iterdir())
        if split in limits:
            random.Random(args.seed).shuffle(images)
            images = sorted(images[: limits[split]])
        crop_dir = out / "crops" / split
        crop_dir.mkdir(parents=True, exist_ok=True)
        for i, img_path in enumerate(images, 1):
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            boxes = yolo_boxes(det / "labels" / split / f"{img_path.stem}.txt", img.shape[1], img.shape[0])
            for idx, box in enumerate(boxes):
                crop = crop_box(img, box, args.pad)
                if crop.size == 0:
                    continue
                lines = split_lines(crop) if is_two_line(crop, args.two_line_ratio) else [crop]
                reads = recognizer.recognize(lines)
                ocr_lines = [t for t, _ in reads]
                text, valid = draft_text(ocr_lines)
                crop_name = f"{split}/{img_path.stem}_{idx}.jpg"
                h = crop.shape[0]
                preview = cv2.resize(crop, (round(crop.shape[1] * 96 / h), 96)) if h else crop
                cv2.imwrite(str(out / "crops" / crop_name), preview)
                rows.append({
                    "split": split, "image": img_path.name, "plate_idx": idx, "crop": crop_name,
                    "text": text, "ocr_text": "/".join(ocr_lines),
                    "conf": f"{float(np.mean([c for _, c in reads])) if reads else 0.0:.3f}",
                    "valid": int(valid), "status": "",
                })
            if i % 200 == 0:
                print(f"{split}: {i}/{len(images)} images")
        print(f"{split}: {sum(r['split'] == split for r in rows)} plates")

    out.mkdir(parents=True, exist_ok=True)
    with open(out / "drafts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    n_valid = sum(r["valid"] for r in rows)
    print(f"{len(rows)} plates, {n_valid} already match a VN template -> {out / 'drafts.csv'}")


if __name__ == "__main__":
    main()
