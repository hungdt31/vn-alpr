"""Train the CRNN line recognizer with CTC loss.

    python scripts/train_crnn.py --config configs/crnn.yaml
    python scripts/train_crnn.py --config configs/crnn.yaml --resume models/crnn/best.pt --epochs 20   # fine-tune
    python scripts/train_crnn.py --config configs/crnn.yaml --eval models/crnn/best.pt
"""

import argparse
import time
from pathlib import Path

import _bootstrap  # noqa: F401
import torch
import yaml
from torch import nn
from torch.utils.data import DataLoader

from alpr.metrics import char_accuracy, plate_accuracy
from alpr.ocr.crnn.charset import Charset
from alpr.ocr.crnn.dataset import LineDataset, collate
from alpr.ocr.crnn.model import CRNN


@torch.no_grad()
def evaluate(model, loader, charset, device):
    model.eval()
    preds, gts = [], []
    for images, _, _, texts in loader:
        probs = model(images.to(device)).softmax(2).cpu().numpy()
        preds += [t for t, _ in charset.decode_greedy(probs)]
        gts += texts
    return plate_accuracy(preds, gts), char_accuracy(preds, gts), list(zip(preds, gts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/crnn.yaml")
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--lr", type=float)
    ap.add_argument("--resume", help="checkpoint to start from (fine-tuning)")
    ap.add_argument("--eval", metavar="WEIGHTS", help="only evaluate WEIGHTS on val_dirs")
    ap.add_argument("--train-dirs", nargs="+", help="override train_dirs")
    ap.add_argument("--val-dirs", nargs="+", help="override val_dirs")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    cfg["epochs"] = args.epochs or cfg["epochs"]
    cfg["lr"] = args.lr or cfg["lr"]
    cfg["train_dirs"] = args.train_dirs or cfg["train_dirs"]
    cfg["val_dirs"] = args.val_dirs or cfg["val_dirs"]
    device = args.device

    init_path = args.eval or args.resume
    init = torch.load(init_path, map_location="cpu", weights_only=False) if init_path else None
    charset = Charset(init["meta"]["chars"] if init else Charset().chars)
    meta = {"chars": charset.chars, "img_h": cfg["img_h"], "img_w": cfg["img_w"], "hidden": cfg["hidden"]}

    model = CRNN(charset.num_classes, hidden=cfg["hidden"]).to(device)
    if init:
        model.load_state_dict(init["model"])

    val_ds = LineDataset(cfg["val_dirs"], charset, cfg["img_h"], cfg["img_w"])
    val_dl = DataLoader(val_ds, cfg["batch_size"], shuffle=False, num_workers=cfg["num_workers"], collate_fn=collate)
    if args.eval:
        acc, cacc, pairs = evaluate(model, val_dl, charset, device)
        print(f"line acc={acc:.4f}  char acc={cacc:.4f}  ({len(val_ds)} lines)")
        for p, g in [x for x in pairs if x[0] != x[1]][:20]:
            print(f"  pred={p:12s} gt={g}")
        return

    train_ds = LineDataset(cfg["train_dirs"], charset, cfg["img_h"], cfg["img_w"], augment=cfg["augment"])
    if len(train_ds) == 0:
        raise SystemExit(f"No training data found in {cfg['train_dirs']}")
    print(f"train {len(train_ds)} lines, val {len(val_ds)} lines, device {device}")
    train_dl = DataLoader(train_ds, cfg["batch_size"], shuffle=True, num_workers=cfg["num_workers"],
                          collate_fn=collate, drop_last=True)

    criterion = nn.CTCLoss(blank=Charset.BLANK, zero_infinity=True)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg["lr"], total_steps=cfg["epochs"] * len(train_dl))

    out = Path(cfg["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    best_acc = -1.0
    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        t0, total = time.time(), 0.0
        for images, targets, lengths, _ in train_dl:
            log_probs = model(images.to(device)).log_softmax(2)
            input_lengths = torch.full((images.size(0),), log_probs.size(0), dtype=torch.long)
            loss = criterion(log_probs.cpu(), targets, input_lengths, lengths)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            sched.step()
            total += loss.item()

        msg = f"epoch {epoch:3d}  loss {total / len(train_dl):.4f}  {time.time() - t0:.0f}s"
        if len(val_ds):
            acc, cacc, _ = evaluate(model, val_dl, charset, device)
            msg += f"  val line acc {acc:.4f}  char acc {cacc:.4f}"
        else:
            acc = -epoch  # no validation data: keep the latest
        if acc > best_acc:
            best_acc = acc
            torch.save({"model": model.state_dict(), "meta": meta, "epoch": epoch}, out)
            msg += "  *saved*"
        print(msg, flush=True)
    print(f"best -> {out}")


if __name__ == "__main__":
    main()
