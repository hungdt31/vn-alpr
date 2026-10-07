# 🚗 VN-ALPR — Nhận diện biển số xe Việt Nam

Hệ thống nhận diện biển số xe Việt Nam end-to-end cho cổng bãi đỗ xe. Hỗ trợ **biển 1 dòng và 2 dòng**, chạy **realtime** trên video, ghi nhận lượt vào/ra và tính thời gian gửi xe.

**YOLO** (phát hiện) → **tách dòng** → **CRNN/PaddleOCR** (đọc ký tự) → **hậu xử lý theo định dạng biển VN** → **ByteTrack + voting** (video) → **FastAPI + Streamlit**

<!-- TODO: thay bằng GIF demo thật -->
<!-- ![demo](docs/demo.gif) -->

## Kết quả

> ⚠️ Điền số liệu thật sau khi train (xem `outputs/ablation.csv`). Mọi số liệu đo trên tập test riêng, gồm ảnh tự thu thập.

| Cấu hình | Plate Acc | Plate Acc 1 dòng | Plate Acc 2 dòng | FPS (T4) | FPS (CPU) |
|----------|-----------|------------------|------------------|----------|-----------|
| YOLO + PaddleOCR | | | | | |
| YOLO + PaddleOCR + hậu xử lý | | | | | |
| YOLO + CRNN | | | | | |
| **YOLO + CRNN + hậu xử lý** | | | | | |
| + ONNX / TensorRT FP16 | | | | | |

Detector trên tập test: mAP@0.5 = __, mAP@0.5:0.95 = __

## Kiến trúc

```
Camera ─▶ YOLO detector ─▶ Crop + deskew ─▶ 1 dòng / 2 dòng? ─▶ OCR từng dòng ─▶ Hậu xử lý VN ─▶ Tracking + voting ─▶ API / UI / SQLite
```

| Thành phần | Mô tả | Code |
|------------|-------|------|
| Detector | YOLO11/YOLOv8 fine-tune, tắt lật ngang (fliplr) vì biển có chữ | [detection/detector.py](src/alpr/detection/detector.py) |
| Tiền xử lý | Crop có padding, deskew theo minAreaRect, tách 2 dòng bằng horizontal projection | [preprocess.py](src/alpr/preprocess.py) |
| OCR | CRNN (CNN + BiLSTM + CTC) tự train, hoặc PaddleOCR làm baseline | [ocr/](src/alpr/ocr/) |
| Hậu xử lý | Chuẩn hoá, khớp template biển VN, sửa ký tự dễ nhầm theo vị trí (`O↔0`, `B↔8`, `S↔5`…) | [plate_format.py](src/alpr/postprocess/plate_format.py) |
| Video | ByteTrack + bỏ phiếu có trọng số qua nhiều frame. Xe đã xác nhận thì bỏ qua OCR để tiết kiệm tính toán | [voter.py](src/alpr/tracking/voter.py), [pipeline.py](src/alpr/pipeline.py) |
| Ứng dụng | REST API, giao diện Streamlit, log vào/ra SQLite (chống ghi trùng, tính thời gian gửi) | [app/](app/) |

### Hậu xử lý theo định dạng biển VN

| Template | Ví dụ | Loại |
|----------|-------|------|
| `DDL` + 4–5 số | `51G-123.45` | Ô tô |
| `DDLL` + 4–5 số | `30LD-123.45` | Ô tô (2 chữ seri) |
| `DDLD` + 4–5 số | `59-X1 123.45` | Xe máy |
| `DDMĐD` + 4–5 số | `29-MĐ1 123.45` | Xe máy điện |

OCR đọc `S1G-I23.45` → hậu xử lý ra `51G-123.45`. Thuật toán thử mọi template, chỉ sửa ký tự khi vị trí đó bắt buộc là số hoặc chữ, rồi chọn template cần ít lần sửa nhất. Với biển 2 dòng, độ dài dòng 1 cho biết seri kết thúc ở đâu.

## Cài đặt

```bash
python -m venv .venv && .venv\Scripts\activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
# tuỳ chọn, baseline PaddleOCR:
pip install -r requirements-paddle.txt
```

## Sử dụng

Đặt model đã train vào `models/detector/best.pt` và `models/crnn/best.pt` (xem [models/README.md](models/README.md)).

```bash
# Demo realtime webcam / video / RTSP, ghi log vào/ra
python scripts/run_camera.py --source 0 --direction in
python scripts/run_camera.py --source data/demo.mp4 --save outputs/demo_out.mp4

# REST API: http://localhost:8000/docs
uvicorn app.api.main:app --port 8000

# Giao diện web: http://localhost:8501
streamlit run app/ui/streamlit_app.py

# Hoặc chạy cả hai bằng Docker
docker compose up --build
```

### Giao diện React (Neobrutalism)

[web/](web/) là giao diện React + Vite + Tailwind v4, dùng component từ [neobrutalism.com](https://neobrutalism.com) (cài qua shadcn CLI). Khác với Streamlit, giao diện này **gọi vào REST API**, nên phải chạy API trước. Ở chế độ dev, Vite chuyển `/api/*` sang `http://localhost:8000`.

```bash
uvicorn app.api.main:app --port 8000      # terminal 1, ở thư mục gốc
cd web && npm install && npm run dev      # terminal 2: http://localhost:5173
```

Gồm 4 tab: nhận diện ảnh (vẽ khung và biển số lên ảnh), cổng vào/ra (ghi lượt, tính thời gian gửi), lịch sử (tìm theo biển số) và xe đang trong bãi. Thêm component khác bằng `npx shadcn@latest add @neobrutalism/<tên>`.

| API | Mô tả |
|-----|-------|
| `POST /recognize` | Upload ảnh, trả danh sách biển số (box, text, confidence, 1/2 dòng) |
| `POST /gate/{in\|out}` | Nhận diện và ghi lượt vào/ra. Khi xe ra, trả thêm `duration_s` |
| `GET /events?plate=51G` | Tra cứu lịch sử |
| `GET /parked` | Xe đang trong bãi |

## Train

Không có GPU thì dùng notebook Colab [notebooks/train_colab.ipynb](notebooks/train_colab.ipynb). Định dạng dữ liệu xem ở [data/README.md](data/README.md).

```bash
# 1. Chia dữ liệu (ảnh tự chụp own_* luôn vào test)
python scripts/split_dataset.py --src data/raw --dst data/processed/detection --test-prefix own_

# 2. Detector
python scripts/train_detector.py --model yolo11n.pt --epochs 100
python scripts/train_detector.py --eval models/detector/best.pt

# 3. CRNN: pre-train trên dữ liệu tổng hợp, sau đó fine-tune trên crop thật
python scripts/gen_synthetic.py --n 50000 --out data/synthetic/ocr
python scripts/gen_synthetic.py --n 2000 --out data/synthetic/ocr_val --seed 1
python scripts/train_crnn.py --epochs 20 --train-dirs data/synthetic/ocr --val-dirs data/synthetic/ocr_val
python scripts/make_ocr_crops.py --texts data/raw/texts.csv
python scripts/train_crnn.py --resume models/crnn/best.pt --epochs 30 --lr 0.0005

# 4. Đánh giá end-to-end + ablation (kết quả cộng dồn vào outputs/ablation.csv, ca lỗi ghi ra outputs/errors_*.csv)
python scripts/evaluate.py --images data/processed/detection/images/test --gt data/raw/test_texts.csv --tag "YOLO + CRNN + postprocess"
python scripts/evaluate.py ... --no-postprocess --tag "YOLO + CRNN"

# 5. Export + đo tốc độ
python scripts/export_models.py --detector models/detector/best.pt --crnn models/crnn/best.pt
python scripts/benchmark.py --source data/demo.mp4 --detector models/detector/best.onnx --crnn models/crnn/best.onnx
```

## Test

```bash
pip install -r requirements-dev.txt
pytest -q          # chạy không cần model: detector/recognizer được giả lập
ruff check src app scripts tests
```

## Cấu trúc

```
├── configs/          # pipeline.yaml, crnn.yaml, data_plate.yaml
├── src/alpr/         # thư viện lõi: detection, ocr, postprocess, tracking, pipeline, export
├── app/              # api (FastAPI), db (SQLite), ui (Streamlit)
├── scripts/          # chuẩn bị dữ liệu, train, đánh giá, benchmark, demo camera
├── notebooks/        # train trên Colab
├── tests/            # pytest
└── SPEC.md           # đặc tả dự án
```

## Phân tích lỗi

<!-- TODO: sau khi chạy evaluate.py, phân nhóm các ca sai trong outputs/errors_*.csv -->

| Nhóm lỗi | Số ca | Ví dụ | Hướng cải thiện |
|----------|-------|-------|-----------------|
| Ảnh mờ do chuyển động | | | |
| Nghiêng hoặc góc chụp lớn | | | |
| Chói sáng, ban đêm | | | |
| Tách dòng sai (biển 2 dòng) | | | |
| Nhầm ký tự | | | |

## Hạn chế và hướng phát triển

- Dữ liệu tổng hợp dùng font Hershey của OpenCV, khác font biển số thật. Có thể thay bằng font biển VN để pre-train tốt hơn.
- Chưa tối ưu cho ảnh đêm hoặc camera hồng ngoại.
- Hướng vào/ra hiện cố định theo camera. Có thể suy ra hướng từ quỹ đạo tracking.
