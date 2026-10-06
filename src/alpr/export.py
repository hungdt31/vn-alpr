"""Export models for fast inference: YOLO -> ONNX / TensorRT, CRNN -> ONNX."""

from __future__ import annotations

import json
from pathlib import Path


def export_detector(weights: str | Path, fmt: str = "onnx", imgsz: int = 640, half: bool = False) -> Path:
    """fmt: 'onnx' (CPU/GPU via onnxruntime) or 'engine' (TensorRT, needs an NVIDIA GPU)."""
    from ultralytics import YOLO

    out = YOLO(str(weights)).export(format=fmt, imgsz=imgsz, half=half, dynamic=False, simplify=True)
    return Path(out)


def export_crnn(weights: str | Path, out: str | Path | None = None, opset: int = 17) -> Path:
    """Writes <out>.onnx plus <out>.json (charset and input size) used by CRNNRecognizer."""
    import torch

    from alpr.ocr.crnn.charset import Charset
    from alpr.ocr.crnn.model import CRNN

    weights = Path(weights)
    out = Path(out) if out else weights.with_suffix(".onnx")
    ckpt = torch.load(weights, map_location="cpu", weights_only=False)
    meta = ckpt["meta"]
    model = CRNN(Charset(meta["chars"]).num_classes, hidden=meta["hidden"]).eval()
    model.load_state_dict(ckpt["model"])

    dummy = torch.zeros(2, 1, meta["img_h"], meta["img_w"])
    kwargs = dict(
        input_names=["image"], output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}, "logits": {1: "batch"}}, opset_version=opset,
    )
    try:
        # the dynamo exporter (default in torch >= 2.9) bakes the LSTM batch size into a Reshape
        torch.onnx.export(model, dummy, str(out), dynamo=False, **kwargs)
    except TypeError:  # older torch without the `dynamo` argument
        torch.onnx.export(model, dummy, str(out), **kwargs)
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out
