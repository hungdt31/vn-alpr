"""CRNN inference from a PyTorch checkpoint (.pt) or an ONNX export (.onnx + sidecar .json)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from alpr.ocr.crnn.charset import Charset
from alpr.ocr.crnn.model import prepare_line


def _softmax(x: np.ndarray, axis: int) -> np.ndarray:
    e = np.exp(x - x.max(axis=axis, keepdims=True))
    return e / e.sum(axis=axis, keepdims=True)


class CRNNRecognizer:
    def __init__(self, weights: str | Path, device: str = "cpu"):
        weights = Path(weights)
        if not weights.exists():
            raise FileNotFoundError(f"CRNN weights not found: {weights} (train with scripts/train_crnn.py)")
        self.backend = "onnx" if weights.suffix == ".onnx" else "torch"

        if self.backend == "onnx":
            import onnxruntime as ort

            meta = json.loads(weights.with_suffix(".json").read_text(encoding="utf-8"))
            self.session = ort.InferenceSession(str(weights), providers=ort.get_available_providers())
            self.input_name = self.session.get_inputs()[0].name
        else:
            import torch

            from alpr.ocr.crnn.model import CRNN

            ckpt = torch.load(weights, map_location=device, weights_only=False)
            meta = ckpt["meta"]
            self.model = CRNN(Charset(meta["chars"]).num_classes, hidden=meta["hidden"]).to(device).eval()
            self.model.load_state_dict(ckpt["model"])
            self.device = device

        self.charset = Charset(meta["chars"])
        self.img_h, self.img_w = meta["img_h"], meta["img_w"]

    def _logits(self, batch: np.ndarray) -> np.ndarray:
        if self.backend == "onnx":
            return self.session.run(None, {self.input_name: batch})[0]
        import torch

        with torch.inference_mode():
            return self.model(torch.from_numpy(batch).to(self.device)).cpu().numpy()

    def recognize(self, images: list[np.ndarray]) -> list[tuple[str, float]]:
        if not images:
            return []
        batch = np.stack([prepare_line(img, self.img_h, self.img_w) for img in images]).astype(np.float32)
        return self.charset.decode_greedy(_softmax(self._logits(batch), axis=2))
