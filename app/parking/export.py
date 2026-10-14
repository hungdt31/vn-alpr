"""Turn plates confirmed by drivers at the entry gate into a CRNN line dataset (human-in-the-loop labels).

Output is the same format as make_ocr_crops.py (<out>/*.png + labels.tsv), so the folder can be added to
`train_dirs` in configs/crnn.yaml and used by the fine-tuning step.
"""

from __future__ import annotations

from pathlib import Path

import cv2

from alpr.postprocess.plate_format import normalize
from alpr.preprocess import crop_box, is_two_line, split_lines


def plate_lines(plate: str, display: str) -> tuple[str, str]:
    """(series line, number line), e.g. 54L19999 shown as "54-L1 9999" -> (54L1, 9999).

    The split comes from the stored display, not the text: 54L19999 is also a valid 54L-199.99, so only the
    line layout the driver confirmed tells the two apart. 2-line displays have a space, 1-line ones a "-".
    """
    head = display.split(" ")[0] if " " in display else display.split("-")[0]
    head = normalize(head)
    return head, plate[len(head):]


def export_line_dataset(captures: list[dict], out: str | Path, pad: float = 0.05,
                        two_line_ratio: float = 2.5) -> int:
    """captures: ParkingLot.labeled_captures(). Returns the number of line images written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, c in enumerate(captures):
        img = cv2.imread(c["path"])
        if img is None:
            continue
        crop = crop_box(img, tuple(c["entry_box"]), pad)
        if crop.size == 0:
            continue
        if is_two_line(crop, two_line_ratio):
            items = list(zip(split_lines(crop), plate_lines(c["plate"], c["display"])))
        else:
            items = [(crop, c["plate"])]
        for li, (line_img, text) in enumerate(items):
            name = f"gate_{i:05d}_{li}.png"
            cv2.imwrite(str(out / name), line_img)
            rows.append(f"{name}\t{text}")
    (out / "labels.tsv").write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return len(rows)
