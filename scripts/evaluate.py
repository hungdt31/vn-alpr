"""End-to-end evaluation (detector + OCR + post-processing) and ablation logging.

GT CSV columns: image,text   (one row per plate; 2-line plates may use "/" between lines)

    python scripts/evaluate.py --images data/processed/detection/images/test --gt data/raw/test_texts.csv \
        --tag "YOLO + CRNN + postprocess"
    python scripts/evaluate.py ... --no-postprocess --tag "YOLO + CRNN"
    python scripts/evaluate.py ... --ocr paddle --tag "YOLO + PaddleOCR"

Writes outputs/errors_<tag>.csv for error analysis and appends a row to outputs/ablation.csv.
"""

import argparse
import csv
import re
import time
from collections import defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401
import cv2

from alpr.config import load_config
from alpr.metrics import char_accuracy, levenshtein, plate_accuracy
from alpr.pipeline import ALPRPipeline
from alpr.postprocess.plate_format import normalize


def match(preds: list, gts: list[str]) -> list[tuple[str, object]]:
    """Greedy one-to-one matching of GT texts to predictions by edit distance. Missing -> None."""
    pairs, used = [], set()
    for gt in gts:
        best, best_d = None, None
        for i, p in enumerate(preds):
            if i in used:
                continue
            d = levenshtein(p.text, normalize(gt))
            if best_d is None or d < best_d:
                best, best_d = i, d
        if best is not None:
            used.add(best)
            pairs.append((gt, preds[best]))
        else:
            pairs.append((gt, None))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--config", default="configs/pipeline.yaml")
    ap.add_argument("--ocr", choices=["crnn", "paddle"], help="override OCR engine")
    ap.add_argument("--no-postprocess", action="store_true")
    ap.add_argument("--no-deskew", action="store_true")
    ap.add_argument("--tag", default="default")
    ap.add_argument("--out-dir", default="outputs")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.ocr:
        cfg.ocr.engine = args.ocr
    cfg.postprocess.enabled = not args.no_postprocess
    cfg.postprocess.deskew = not args.no_deskew
    pipeline = ALPRPipeline.from_config(cfg)

    gts: dict[str, list[str]] = defaultdict(list)
    with open(args.gt, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gts[row["image"]].append(row["text"])

    rows, pred_texts, gt_texts, kinds = [], [], [], []
    n_pred, n_detected, elapsed = 0, 0, 0.0
    for name, texts in gts.items():
        img = cv2.imread(str(Path(args.images) / name))
        if img is None:
            print(f"warn: cannot read {name}")
            continue
        t0 = time.perf_counter()
        preds = pipeline.process_image(img)
        elapsed += time.perf_counter() - t0
        n_pred += len(preds)
        for gt, p in match(preds, texts):
            pred = p.text if p else ""
            n_detected += p is not None
            pred_texts.append(pred)
            gt_texts.append(gt)
            kinds.append("2-line" if "/" in gt else "1-line")
            if normalize(pred) != normalize(gt):
                rows.append({"image": name, "gt": normalize(gt), "pred": pred,
                             "raw": "|".join(p.raw_lines) if p else "", "detected": p is not None,
                             "two_line_pred": p.two_line if p else "", "ocr_conf": f"{p.ocr_conf:.3f}" if p else ""})

    n = len(gt_texts)
    if n == 0:
        raise SystemExit("No ground-truth plates evaluated")
    summary = {
        "tag": args.tag,
        "plates": n,
        "det_recall": n_detected / n,
        "false_pos": max(0, n_pred - n_detected),
        "plate_acc": plate_accuracy(pred_texts, gt_texts),
        "char_acc": char_accuracy(pred_texts, gt_texts),
        "ms_per_image": 1000 * elapsed / len(gts),
    }
    for kind in ("1-line", "2-line"):
        idx = [i for i, k in enumerate(kinds) if k == kind]
        if idx:
            summary[f"plate_acc_{kind}"] = plate_accuracy([pred_texts[i] for i in idx], [gt_texts[i] for i in idx])

    for k, v in summary.items():
        print(f"{k:18s} {v:.4f}" if isinstance(v, float) else f"{k:18s} {v}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", args.tag).strip("_").lower()
    with open(out / f"errors_{slug}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["image", "gt", "pred", "raw", "detected", "two_line_pred", "ocr_conf"])
        w.writeheader()
        w.writerows(rows)
    ablation = out / "ablation.csv"
    fields = ["tag", "plates", "det_recall", "false_pos", "plate_acc", "plate_acc_1-line", "plate_acc_2-line",
              "char_acc", "ms_per_image"]
    new = not ablation.exists()
    with open(ablation, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in summary.items()})
    print(f"errors -> {out / f'errors_{slug}.csv'}   ablation row -> {ablation}")


if __name__ == "__main__":
    main()
