"""CRNN (CNN + BiLSTM + CTC) for single text lines, input 1 x 32 x 128 grayscale."""

from __future__ import annotations

import cv2
import numpy as np
import torch
from torch import nn


def _conv(cin: int, cout: int) -> list[nn.Module]:
    return [nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]


class CRNN(nn.Module):
    def __init__(self, num_classes: int, hidden: int = 128):
        super().__init__()
        self.cnn = nn.Sequential(
            *_conv(1, 64), nn.MaxPool2d(2, 2),  # H/2,  W/2
            *_conv(64, 128), nn.MaxPool2d(2, 2),  # H/4,  W/4
            *_conv(128, 256), *_conv(256, 256), nn.MaxPool2d((2, 1)),  # H/8
            *_conv(256, 256), nn.MaxPool2d((2, 1)),  # H/16
            nn.Dropout2d(0.1),
        )
        self.rnn = nn.LSTM(256, hidden, num_layers=2, bidirectional=True, dropout=0.1)
        self.fc = nn.Linear(2 * hidden, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B, 1, H, W] -> logits [T, B, K] with T = W / 4."""
        # mean over height instead of AdaptiveAvgPool2d((1, None)), which ONNX cannot export
        f = self.cnn(x).mean(dim=2).permute(2, 0, 1)  # [T, B, C]
        f, _ = self.rnn(f)
        return self.fc(f)


def prepare_line(img: np.ndarray, img_h: int = 32, img_w: int = 128) -> np.ndarray:
    """Grayscale, resize keeping aspect ratio, right-pad to img_w, scale to [-1, 1]. Returns [1, H, W]."""
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    new_w = max(1, min(img_w, round(w * img_h / max(h, 1))))
    resized = cv2.resize(gray, (new_w, img_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((img_h, img_w), int(np.median(resized[:, -1])), np.uint8)
    canvas[:, :new_w] = resized
    return ((canvas.astype(np.float32) / 255.0 - 0.5) / 0.5)[None]
