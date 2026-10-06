"""Fine-tune a YOLO plate detector.

    python scripts/train_detector.py --model yolo11n.pt --epochs 100 --batch 32
    python scripts/train_detector.py --eval models/detector/best.pt      # mAP on the test split
"""

import argparse
import shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="configs/data_plate.yaml")
    ap.add_argument("--model", default="yolo11n.pt", help="pretrained checkpoint (yolov8n.pt, yolo11s.pt, ...)")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None)
    ap.add_argument("--name", default="plate")
    ap.add_argument("--out", default="models/detector/best.pt")
    ap.add_argument("--eval", metavar="WEIGHTS", help="only evaluate WEIGHTS on the test split")
    args = ap.parse_args()

    from ultralytics import YOLO

    if args.eval:
        m = YOLO(args.eval).val(data=args.data, split="test", imgsz=args.imgsz, device=args.device)
        print(f"test mAP50={m.box.map50:.4f}  mAP50-95={m.box.map:.4f}  P={m.box.mp:.4f}  R={m.box.mr:.4f}")
        return

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project="runs/detector",
        name=args.name,
        patience=20,
        # plates contain text: never mirror them
        fliplr=0.0,
        degrees=10.0,
        perspective=0.0005,
        hsv_v=0.5,
        mosaic=1.0,
        close_mosaic=10,
    )
    best = Path(model.trainer.best)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, args.out)
    print(f"best weights -> {args.out}")


if __name__ == "__main__":
    main()
