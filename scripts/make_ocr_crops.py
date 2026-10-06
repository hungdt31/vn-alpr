"""Build CRNN line datasets from detection labels + plate texts.

texts CSV columns: image,plate_idx,text
    image      file name in <images> (e.g. 0001.jpg)
    plate_idx  0-based row index of the box in the YOLO label file
    text       plate text; separate lines of a 2-line plate with "/" (e.g. "59-X1/123.45")

Output per split: <out>/<split>/*.png + labels.tsv (one image per text line).
Plates labelled with "/" are split into lines with the same algorithm used at inference.

    python scripts/make_ocr_crops.py --detection data/processed/detection --texts data/raw/texts.csv \
        --out data/processed/ocr
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401
import cv2

from alpr.postprocess.plate_format import normalize
from alpr.preprocess import crop_box, split_lines


def yolo_boxes(label_path: Path, w: int, h: int) -> list[tuple[int, int, int, int]]:
    boxes = []
    if not label_path.exists():
        return boxes
    for line in label_path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        cx, cy, bw, bh = (float(v) for v in parts[1:5])
        boxes.append((int((cx - bw / 2) * w), int((cy - bh / 2) * h), int((cx + bw / 2) * w), int((cy + bh / 2) * h)))
    return boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detection", default="data/processed/detection")
    ap.add_argument("--texts", default="data/raw/texts.csv")
    ap.add_argument("--out", default="data/processed/ocr")
    ap.add_argument("--pad", type=float, default=0.05)
    args = ap.parse_args()

    texts: dict[str, dict[int, str]] = defaultdict(dict)
    with open(args.texts, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            texts[row["image"]][int(row["plate_idx"])] = row["text"]

    det = Path(args.detection)
    for split in ("train", "val", "test"):
        img_dir = det / "images" / split
        if not img_dir.exists():
            continue
        out = Path(args.out) / split
        out.mkdir(parents=True, exist_ok=True)
        rows = []
        for img_path in sorted(img_dir.iterdir()):
            if img_path.name not in texts:
                continue
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            boxes = yolo_boxes(det / "labels" / split / f"{img_path.stem}.txt", img.shape[1], img.shape[0])
            for idx, text in texts[img_path.name].items():
                if idx >= len(boxes):
                    print(f"warn: {img_path.name} has no box #{idx}")
                    continue
                crop = crop_box(img, boxes[idx], args.pad)
                line_texts = [normalize(t) for t in text.split("/")]
                line_imgs = split_lines(crop) if len(line_texts) == 2 else [crop]
                for li, (line_img, line_text) in enumerate(zip(line_imgs, line_texts)):
                    name = f"{img_path.stem}_{idx}_{li}.png"
                    cv2.imwrite(str(out / name), line_img)
                    rows.append(f"{name}\t{line_text}")
        (out / "labels.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(f"{split:5s}: {len(rows)} line images -> {out}")


if __name__ == "__main__":
    main()
