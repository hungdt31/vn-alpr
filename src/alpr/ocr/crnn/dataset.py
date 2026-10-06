"""Line-image dataset. Each directory holds images plus `labels.tsv` with `relative_path<TAB>text`."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from alpr.ocr.crnn.charset import Charset
from alpr.ocr.crnn.model import prepare_line
from alpr.postprocess.plate_format import normalize
from alpr.synth import augment


def read_labels(root: str | Path) -> list[tuple[Path, str]]:
    root = Path(root)
    items = []
    with open(root / "labels.tsv", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or "\t" not in line:
                continue
            rel, text = line.split("\t", 1)
            items.append((root / rel, normalize(text)))
    return items


class LineDataset(Dataset):
    def __init__(self, dirs: list[str | Path], charset: Charset, img_h=32, img_w=128, augment=False, seed=0):
        self.items = [it for d in dirs if (Path(d) / "labels.tsv").exists() for it in read_labels(d)]
        self.items = [(p, t) for p, t in self.items if t]
        self.charset, self.img_h, self.img_w = charset, img_h, img_w
        self.augment = augment
        self.rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i):
        path, text = self.items[i]
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(path)
        if self.augment:
            img = augment(img, self.rng, strength=0.7)
        x = torch.from_numpy(prepare_line(img, self.img_h, self.img_w))
        return x, torch.tensor(self.charset.encode(text), dtype=torch.long), text


def collate(batch):
    images, targets, texts = zip(*batch)
    lengths = torch.tensor([len(t) for t in targets], dtype=torch.long)
    return torch.stack(images), torch.cat(targets), lengths, list(texts)
