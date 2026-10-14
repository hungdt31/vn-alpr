"""Review the OCR drafts from draft_texts.py and export texts.csv / test_texts.csv.

    streamlit run scripts/review_texts.py                       # reads data/drafts
    streamlit run scripts/review_texts.py -- --drafts path/to/drafts

Each page shows plate crops with their draft text. Fix the wrong ones, tick "Bỏ" for unreadable plates,
then "Lưu trang" marks the whole page as reviewed (saved to drafts.csv right away, so you can stop any time).
"""

import argparse
import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401
import streamlit as st

from alpr.postprocess.plate_format import parse_plate

FIELDS = ["split", "image", "plate_idx", "crop", "text", "ocr_text", "conf", "valid", "status"]
STATUS_LABEL = {"": "chưa duyệt", "ok": "đã duyệt", "skip": "bỏ qua"}


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)  # never leave a half-written drafts.csv


def check(text: str) -> tuple[bool, str]:
    """(valid, display) of a label as typed; 2-line plates use "/" between lines."""
    plate = parse_plate([t for t in text.split("/") if t.strip()])
    return plate.valid, plate.display


def export(rows: list[dict], out: Path, pseudo_conf: float | None) -> tuple[int, int, int]:
    """texts.csv: reviewed plates (+ confident unreviewed train drafts if pseudo_conf is set).
    test_texts.csv: test images whose plates were all reviewed, so a missing GT never counts as an error."""
    def use_for_training(r: dict) -> bool:
        if r["status"] == "ok":
            return True
        return (pseudo_conf is not None and r["status"] == "" and r["split"] == "train"
                and r["valid"] == "1" and float(r["conf"]) >= pseudo_conf)

    train_rows = [r for r in rows if use_for_training(r)]
    with open(out / "texts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "plate_idx", "text"])
        w.writerows([r["image"], r["plate_idx"], r["text"]] for r in train_rows)

    by_image = defaultdict(list)
    for r in rows:
        if r["split"] == "test":
            by_image[r["image"]].append(r)
    test_rows = [r for plates in by_image.values() if all(p["status"] in ("ok", "skip") for p in plates)
                 for r in plates if r["status"] == "ok"]
    with open(out / "test_texts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "text"])
        w.writerows([r["image"], r["text"]] for r in test_rows)
    n_pseudo = sum(r["status"] == "" for r in train_rows)
    return len(train_rows), n_pseudo, len(test_rows)


ap = argparse.ArgumentParser()
ap.add_argument("--drafts", default="data/drafts")
args = ap.parse_args()
drafts = Path(args.drafts)
csv_path = drafts / "drafts.csv"

st.set_page_config(page_title="Duyệt nhãn biển số", page_icon="🏷️", layout="wide")
st.title("🏷️ Duyệt nhãn chữ biển số")
if not csv_path.exists():
    st.error(f"Không thấy {csv_path}. Chạy scripts/draft_texts.py trước (xem notebook, bước 4b).")
    st.stop()

rows = load(csv_path)

with st.sidebar:
    st.header("Tiến độ")
    for split in ("train", "val", "test"):
        c = Counter(r["status"] for r in rows if r["split"] == split)
        total = sum(c.values())
        if total:
            done = c["ok"] + c["skip"]
            st.progress(done / total, text=f"{split}: {done}/{total} đã xử lý ({c['skip']} bỏ qua)")
    st.header("Lọc")
    split = st.selectbox(
        "Tập", ["test", "train", "val", "tất cả"], help="Duyệt tập test trước: số liệu đánh giá cần nhãn chính xác."
    )
    status = st.selectbox("Trạng thái", ["chưa duyệt", "đã duyệt", "bỏ qua", "tất cả"])
    order = st.selectbox("Sắp xếp", ["độ tin cậy thấp trước", "độ tin cậy cao trước", "theo tên ảnh"])
    per_page = st.select_slider("Số biển mỗi trang", [8, 12, 16, 24, 32], value=16)

status_key = {v: k for k, v in STATUS_LABEL.items()}
view = [i for i, r in enumerate(rows)
        if (split == "tất cả" or r["split"] == split) and (status == "tất cả" or r["status"] == status_key[status])]
if order == "theo tên ảnh":
    view.sort(key=lambda i: (rows[i]["image"], int(rows[i]["plate_idx"])))
else:
    view.sort(key=lambda i: float(rows[i]["conf"]), reverse=order == "độ tin cậy cao trước")

n_pages = max(1, -(-len(view) // per_page))
page = st.number_input(f"Trang (tổng {n_pages}, {len(view)} biển)", 1, n_pages, 1) - 1
page_ids = view[page * per_page:(page + 1) * per_page]

if not page_ids:
    st.success("Không còn biển nào trong bộ lọc này.")
else:
    st.caption("Biển 2 dòng ghi dạng `59-X1/123.45`. Dấu `-` và `.` không bắt buộc.")
    with st.form("page"):
        cols = st.columns(4)
        for n, i in enumerate(page_ids):
            r = rows[i]
            with cols[n % 4]:
                st.image(str(drafts / "crops" / r["crop"]), width="stretch")
                st.text_input("Chữ trên biển", r["text"], key=f"text_{r['crop']}", label_visibility="collapsed")
                valid, display = check(r["text"])
                hint = f"✅ {display}" if valid else "⚠️ không khớp mẫu biển VN"
                st.caption(f"{hint} · OCR {float(r['conf']):.2f} · {STATUS_LABEL[r['status']]}")
                st.checkbox("Bỏ (không đọc được)", r["status"] == "skip", key=f"skip_{r['crop']}")
        if st.form_submit_button("💾 Lưu trang này (đánh dấu đã duyệt)", type="primary", width="stretch"):
            for i in page_ids:
                r = rows[i]
                r["text"] = st.session_state[f"text_{r['crop']}"].strip()
                skip = st.session_state[f"skip_{r['crop']}"] or not r["text"]
                r["status"] = "skip" if skip else "ok"
                r["valid"] = str(int(check(r["text"])[0]))
            save(csv_path, rows)
            st.rerun()

st.divider()
st.header("Xuất nhãn")
pseudo = st.checkbox(
    "Dùng thêm nhãn nháp chưa duyệt cho tập train (pseudo-label)",
    help="Chỉ lấy những biển khớp mẫu biển VN và có độ tin cậy OCR cao. "
    "Tập val và test luôn chỉ dùng nhãn đã duyệt, để số liệu chọn mô hình và đánh giá đáng tin.",
)
conf = st.slider("Độ tin cậy tối thiểu", 0.5, 1.0, 0.95, 0.01, disabled=not pseudo)
if st.button("Xuất texts.csv và test_texts.csv"):
    n_train, n_pseudo, n_test = export(rows, drafts, conf if pseudo else None)
    st.success(f"texts.csv: {n_train} biển ({n_pseudo} nhãn nháp). test_texts.csv: {n_test} biển.  →  {drafts}")
    for name in ("texts.csv", "test_texts.csv"):
        st.download_button(f"Tải {name}", (drafts / name).read_bytes(), file_name=name, mime="text/csv")
