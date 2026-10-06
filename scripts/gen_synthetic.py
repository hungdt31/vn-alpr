"""Generate synthetic plate line images for CRNN pre-training.

    python scripts/gen_synthetic.py --n 50000 --out data/synthetic/ocr
"""

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401
import cv2
import numpy as np

from alpr.postprocess.plate_format import normalize
from alpr.preprocess import split_lines
from alpr.synth import augment, random_plate, render_plate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000, help="number of plates (2-line plates give 2 images)")
    ap.add_argument("--out", default="data/synthetic/ocr")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.n):
        lines = random_plate(rng)
        plate = augment(render_plate(lines, rng), rng)
        images = split_lines(plate) if len(lines) == 2 else [plate]
        for li, (img, text) in enumerate(zip(images, lines)):
            name = f"syn_{i:06d}_{li}.png"
            cv2.imwrite(str(out / name), cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
            rows.append(f"{name}\t{normalize(text)}")
        if (i + 1) % 5000 == 0:
            print(f"{i + 1}/{args.n}")
    (out / "labels.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} line images -> {out}")


if __name__ == "__main__":
    main()
