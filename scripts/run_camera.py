"""Realtime gate demo: webcam / RTSP / video file -> tracked plates -> entry/exit log.

    python scripts/run_camera.py --source 0 --direction in
    python scripts/run_camera.py --source rtsp://user:pass@ip/stream --direction out --no-show
    python scripts/run_camera.py --source data/demo.mp4 --save outputs/demo_out.mp4
"""

import argparse
import time

import _bootstrap  # noqa: F401
import cv2

from alpr.pipeline import ALPRPipeline
from alpr.visualize import draw_results
from app.db.repository import EventRepository


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0", help="camera index, video path or RTSP url")
    ap.add_argument("--config", default="configs/pipeline.yaml")
    ap.add_argument("--direction", choices=["in", "out"], default="in")
    ap.add_argument("--gate", default="main")
    ap.add_argument("--db", default="data/alpr.db")
    ap.add_argument("--save", help="write annotated video here")
    ap.add_argument("--no-show", action="store_true")
    args = ap.parse_args()

    pipeline = ALPRPipeline.from_config(args.config)
    repo = EventRepository(args.db)
    cap = cv2.VideoCapture(int(args.source) if args.source.isdigit() else args.source)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open source {args.source}")

    writer = None
    idx, fps, t_prev = 0, 0.0, time.perf_counter()

    def log(events):
        for e in events:
            ev = repo.add_event(e.text, e.display, args.direction, e.confidence, gate=args.gate)
            if ev:
                extra = f"  parked {ev['duration_s'] // 60} min" if "duration_s" in ev else ""
                print(f"[{ev['created_at']}] {args.direction.upper():3s} {e.display}  conf={e.confidence:.2f}{extra}")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            results, events = pipeline.process_frame(frame, idx)
            log(events)

            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 / max(now - t_prev, 1e-6) if idx else 0.0
            t_prev = now
            vis = draw_results(frame, results, fps)

            if args.save:
                if writer is None:
                    h, w = vis.shape[:2]
                    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25
                    writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), src_fps, (w, h))
                writer.write(vis)
            if not args.no_show:
                cv2.imshow("VN-ALPR (q to quit)", vis)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            idx += 1
    finally:
        log(pipeline.finish_video(idx))
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
