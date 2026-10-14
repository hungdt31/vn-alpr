"""Where gate camera snapshots are kept on disk."""

from __future__ import annotations

from pathlib import Path


class ImageStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, capture_id: int, data: bytes) -> str:
        path = self.root / f"{capture_id:06d}.jpg"
        path.write_bytes(data)
        return str(path)
