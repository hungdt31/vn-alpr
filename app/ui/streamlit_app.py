"""Streamlit demo.  Run:  streamlit run app/ui/streamlit_app.py"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from alpr.pipeline import ALPRPipeline  # noqa: E402
from alpr.postprocess.plate_format import normalize  # noqa: E402
from alpr.visualize import draw_results  # noqa: E402
from app.db.repository import EventRepository  # noqa: E402

st.set_page_config(page_title="VN-ALPR", page_icon="🚗", layout="wide")


@st.cache_resource
def load_pipeline(config: str) -> ALPRPipeline:
    return ALPRPipeline.from_config(config)


@st.cache_resource
def load_repo(path: str) -> EventRepository:
    return EventRepository(path)


config_path = os.getenv("ALPR_CONFIG", str(ROOT / "configs/pipeline.yaml"))
repo = load_repo(os.getenv("ALPR_DB", str(ROOT / "data/alpr.db")))

st.title("🚗 Nhận diện biển số xe Việt Nam")
try:
    pipeline = load_pipeline(config_path)
except FileNotFoundError as e:
    st.error(f"Chưa có model: {e}")
    st.stop()

with st.sidebar:
    direction = st.radio("Hướng", ["in", "out"], format_func=lambda d: "Vào" if d == "in" else "Ra")
    log_events = st.checkbox("Ghi vào lịch sử", value=True)

tab_img, tab_video, tab_history = st.tabs(["Ảnh", "Video", "Lịch sử"])

with tab_img:
    up = st.file_uploader("Chọn ảnh", type=["jpg", "jpeg", "png"])
    if up:
        img = cv2.imdecode(np.frombuffer(up.read(), np.uint8), cv2.IMREAD_COLOR)
        t0 = time.perf_counter()
        results = pipeline.process_image(img)
        ms = (time.perf_counter() - t0) * 1000
        st.image(cv2.cvtColor(draw_results(img, results), cv2.COLOR_BGR2RGB), use_container_width=True)
        st.caption(f"{len(results)} biển số · {ms:.0f} ms")
        if results:
            st.dataframe(pd.DataFrame([r.to_dict() for r in results]), use_container_width=True)
        if log_events:
            for r in results:
                if r.valid and repo.add_event(r.text, r.display, direction, r.ocr_conf):
                    st.success(f"Đã ghi: {r.display} ({'vào' if direction == 'in' else 'ra'})")

with tab_video:
    vid = st.file_uploader("Chọn video", type=["mp4", "avi", "mov"])
    preview_every = st.slider("Hiển thị mỗi N frame", 1, 30, 5)
    if vid and st.button("Xử lý video"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(vid.name).suffix) as f:
            f.write(vid.read())
        cap = cv2.VideoCapture(f.name)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        frame_box, progress = st.empty(), st.progress(0.0)
        events, idx, t0 = [], 0, time.perf_counter()
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            results, new = pipeline.process_frame(frame, idx)
            events.extend(new)
            if idx % preview_every == 0:
                fps = (idx + 1) / (time.perf_counter() - t0)
                frame_box.image(cv2.cvtColor(draw_results(frame, results, fps), cv2.COLOR_BGR2RGB))
            idx += 1
            progress.progress(min(idx / total, 1.0))
        cap.release()
        events.extend(pipeline.finish_video(idx))
        os.unlink(f.name)
        st.success(f"Xong {idx} frame · {idx / (time.perf_counter() - t0):.1f} FPS · {len(events)} xe")
        if events:
            st.dataframe(pd.DataFrame([e.to_dict() for e in events]), use_container_width=True)
            if log_events:
                for e in events:
                    repo.add_event(e.text, e.display, direction, e.confidence)

with tab_history:
    col1, col2 = st.columns(2)
    q = col1.text_input("Tìm biển số", placeholder="51G12345")
    col1.dataframe(pd.DataFrame(repo.list_events(normalize(q) or None)), use_container_width=True)
    col2.subheader("Đang trong bãi")
    col2.dataframe(pd.DataFrame(repo.parked()), use_container_width=True)
