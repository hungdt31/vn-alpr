# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

VN-ALPR: Vietnamese license plate recognition (1-line and 2-line plates) for parking gates. `SPEC.md` holds the goals and target metrics. The user communicates in Vietnamese, and user-facing docs (README, data/README, SPEC) are in Vietnamese.

## Environment constraints

- The local machine runs Windows and Python 3.13. It has **no GPU, no git and no docker**. Model training happens on Colab through `notebooks/train_colab.ipynb`.
- The local venv `.venv` has only the light test stack: numpy, opencv-headless, pyyaml, fastapi, httpx, pytest, ruff, CPU torch, onnx and onnxruntime. **ultralytics and paddleocr are not installed locally.** Code that needs them imports them lazily inside functions so the rest of the codebase stays importable and testable.
- No trained weights exist in `models/` yet. The pipeline loads them from the paths in `configs/pipeline.yaml`.

## Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q                                   # all tests (~1-2 min, CRNN overfit test is the slow one)
.\.venv\Scripts\python.exe -m pytest -q tests/test_plate_format.py        # one file
.\.venv\Scripts\python.exe -m pytest -q -k "two_line"                     # by name
.\.venv\Scripts\ruff.exe check src app scripts tests                      # lint (CI runs the same)
uvicorn app.api.main:app --port 8000                                      # API (needs models)
cd web && npm run dev                                                     # React UI on :5173 (needs the API)
```

- `pyproject.toml` sets `pythonpath = ["src", "."]`, so tests import `alpr` and `app` without an install.
- Each script in `scripts/` starts with `import _bootstrap` to get the same path setup. Don't remove it. Ruff's isort is configured to place it correctly.
- The training, evaluation and export commands are documented in `README.md` ("Train" section) and in the notebook.

## Architecture

Data flows through the stages below. `src/alpr/pipeline.py::ALPRPipeline` wires them together.

1. **Detect.** `detection/detector.py::PlateDetector` wraps Ultralytics YOLO and accepts `.pt`, `.onnx` or `.engine` weights.
   - `detect()` handles single images.
   - `track()` runs ByteTrack with `persist=True`. Tracker state lasts until `reset_tracker()` is called.
2. **Preprocess.** `preprocess.py` does three things:
   - Crops the plate with padding.
   - Deskews it. The skew angle comes from the long edge of `minAreaRect` box points rather than its returned angle, because that angle's convention differs across OpenCV versions.
   - Decides 1 line versus 2 lines by aspect ratio (`two_line_ratio`). For 2-line plates, it splits at the emptiest row of the middle band using a horizontal projection profile.
3. **OCR.** Any object with `recognize(list[img]) -> list[(text, conf)]` works as a recognizer (the `ocr/__init__.py::Recognizer` protocol), one text line per image. There are two engines:
   - `ocr/crnn/` is a CNN + BiLSTM + CTC model. Input is 1×32×128 grayscale, and CTC blank is index 0.
     - A `.pt` checkpoint stores `{"model", "meta"}`, where `meta` holds the charset, `img_h`, `img_w` and `hidden`.
     - An ONNX export needs a sidecar `.json` file with the same `meta`.
     - Keep the model ONNX-exportable. `AdaptiveAvgPool2d` with a `None` output size cannot be exported, which is why the CNN output is averaged over height with `mean(dim=2)` instead.
     - `export.py` uses `dynamo=False` because the dynamo exporter bakes the LSTM batch size into the graph. `tests/test_crnn.py` guards both points.
   - `ocr/paddle.py` is the baseline and handles both PaddleOCR 2.x and 3.x APIs.
4. **Post-process.** `postprocess/plate_format.py::parse_plate(lines)` turns raw OCR into a plate. This is the core domain logic and is heavily unit-tested.
   - It normalizes the text and tries the VN templates `DDL`, `DDLL`, `DDLD` and `DDLLD` (D = digit, L = letter). `DDLLD` only matches the `MD` series used by electric bikes.
   - Each template is followed by 4–5 digits.
   - Characters are fixed by position: `TO_DIGIT` applies where a digit is required and `TO_LETTER` where a letter is required. The template needing the fewest fixes wins.
   - Template order breaks ties. 1-line plates prefer the car templates; 2-line plates prefer the motorbike template `DDLD`.
   - For 2-line plates, the length of line 1 constrains where the series ends. A match on the joined string that needs fewer fixes overrides this constraint, which covers a split that is off by one character.
   - `fix=False` is the ablation mode.
5. **Video.** `tracking/voter.py::TrackVoter` accumulates confidence-weighted valid readings per track id.
   - It emits one `PlateEvent` per track once `min_hits` and `min_agreement` are met.
   - When a stale track is flushed, it emits its best guess.
   - After a track is confirmed, `process_frame` skips OCR for it.
   - Always call `finish_video()` at the end of a stream. It flushes pending tracks and resets the tracker.
6. **App (`app/`).** Layered: `api` -> `services` -> `domain`, with `infra` implementing storage. `src/alpr` (the ML library) never imports `app`.
   - `domain/`: plain dataclasses and pure rules, no SQL or HTTP. `models.py` (Card, Slot, Capture, Session, GateEvent), `pricing.py` (`Tariff`, `parking_fee`), `matching.py` (`parse_plate_input`, `match_exit_plate`).
   - `services/`: use cases. `GateLog` (per-(plate, direction) cooldown, `duration_s` on an exit after an entry), `ParkingService` (entry, exit check, guard override, lost ticket, stats), `RecognitionService` (decode image, run the pipeline), `training_export`. Services raise `core/errors.py` errors (`NotFound`, `Conflict`, `Invalid`, `Forbidden`, `BadImage`); one handler in `api/main.py` turns them into HTTP responses with `{"detail": message}`. They ask a `Clock` for the time (`infra/clock.py`: `OffsetClock` lets the demo fast-forward).
   - `infra/`: `Database` (one shared connection behind an RLock; `transaction()` nests and only the outermost commits), one repository per table, `ImageStore` for gate snapshots. Schema changes go in a new numbered file in `infra/migrations/` (`NNN_name.sql`); `PRAGMA user_version` records the last one applied. Never edit an applied migration.
   - `container.py` is the only place that wires layers together: `build_container(settings, pipeline=..., clock=...)` for the API and tests, `open_gate_log(db)` for `scripts/run_camera.py`. `core/settings.py::Settings.from_env()` reads `ALPR_CONFIG`, `ALPR_PARKING_CONFIG`, `ALPR_DB` and `configs/parking.yaml`.
   - `api/`: `main.py::create_app(container=None)` builds the container in the lifespan, so importing the module opens nothing; tests pass `build_container(make_settings(tmp_path), pipeline=FakePipeline(), clock=FakeClock())` (`tests/helpers.py`). Routers in `api/routers/`, bodies in `api/schemas.py`. Routes return `XxxOut.model_validate(service_result)`: returning a dataclass directly makes FastAPI run `dataclasses.asdict()`, which drops properties such as `Session.card_code`.
   - `web/` is a React + Vite + Tailwind v4 frontend that calls the REST API; the Vite dev server proxies `/api/*` to `localhost:8000`. UI components come from the neobrutalism shadcn registry (`@neobrutalism` in `web/components.json`, Base UI variant). Archivo Black has no Vietnamese glyphs, so headings use Be Vietnam Pro and `font-plate` (Archivo Black) is only for ASCII plate text. Video files are processed by `scripts/run_camera.py` (there is no video page in the web UI).
   - The parking simulation (`/parking/*`, configured by `configs/parking.yaml`) is `ParkingService`; `training_export` turns driver-corrected plates into a CRNN `labels.tsv` dataset. The exit plate is never typed by the driver: a non-`ok` match needs a guard's `override_reason`. Plate input accepts "/" or a space between the lines of a 2-line plate; the stored `display` keeps that layout, because the text alone is ambiguous (54L19999 is both 54-L1 9999 and 54L-199.99).
   - The 3D scene lives in `web/src/sim/`. `store.ts` is a zustand state machine (one vehicle handled at a time) that drives both the animations and the dialogs. Scene labels are canvas textures (`Sign`), not drei `<Html>`: under StrictMode the first `<Html>` in the scene never mounted. Headless browser screenshots do not capture WebGL, which is why the canvas sets `preserveDrawingBuffer`.

Config is loaded by `config.py`: nested dataclasses built from `configs/pipeline.yaml`. Unknown keys raise an error, so add new fields to the dataclass first.

The data formats are documented in `data/README.md`:
- YOLO labels.
- `texts.csv`, where `/` separates the lines of a 2-line plate.
- `labels.tsv` (`relpath<TAB>text`) for the CRNN line datasets.
- `split_dataset.py --test-prefix own_` always places the self-collected images in the test split.

## Testing approach

Tests never need trained weights or ultralytics. `tests/test_pipeline.py` and `tests/test_app.py` use fake detector, recognizer and pipeline objects. Synthetic plates come from `alpr/synth.py::render_plate`, which uses OpenCV Hershey fonts. `tests/test_crnn.py` skips itself if torch is missing.
