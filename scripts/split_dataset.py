"""Split a YOLO-format detection dataset into train/val/test.

Input:   <src>/images/*.jpg|png   <src>/labels/*.txt   (YOLO: class cx cy w h, normalized)
Output:  <dst>/images/{train,val,test}/  <dst>/labels/{train,val,test}/

Images whose name starts with --test-prefix (e.g. your own photos "own_") always go to test,
so the test set measures performance on data the model never saw from that source.

    python scripts/split_dataset.py --src data/raw --dst data/processed/detection --test-prefix own_
"""

import argparse
import random
import shutil
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/raw")
    ap.add_argument("--dst", default="data/processed/detection")
    ap.add_argument("--val", type=float, default=0.15)
    ap.add_argument("--test", type=float, default=0.15)
    ap.add_argument("--test-prefix", default=None)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    images = sorted(p for p in (src / "images").iterdir() if p.suffix.lower() in IMG_EXT)
    forced_test = [p for p in images if args.test_prefix and p.name.startswith(args.test_prefix)]
    forced = set(forced_test)
    rest = [p for p in images if p not in forced]
    random.Random(args.seed).shuffle(rest)

    n_test = max(0, round(len(images) * args.test) - len(forced_test))
    n_val = round(len(images) * args.val)
    splits = {
        "test": forced_test + rest[:n_test],
        "val": rest[n_test : n_test + n_val],
        "train": rest[n_test + n_val :],
    }

    missing = 0
    for split, files in splits.items():
        (dst / "images" / split).mkdir(parents=True, exist_ok=True)
        (dst / "labels" / split).mkdir(parents=True, exist_ok=True)
        for img in files:
            shutil.copy2(img, dst / "images" / split / img.name)
            label = src / "labels" / f"{img.stem}.txt"
            if label.exists():
                shutil.copy2(label, dst / "labels" / split / label.name)
            else:
                missing += 1  # background image (no plate) - allowed by YOLO
        print(f"{split:5s}: {len(files)} images")
    if missing:
        print(f"note: {missing} images without label file (treated as background)")


if __name__ == "__main__":
    main()
