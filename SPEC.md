# SPEC — Hệ thống nhận diện biển số xe Việt Nam (VN-ALPR)

> Phiên bản: 0.1 (bản nháp) · Ngày: 2026-10-06
> Mục tiêu sử dụng: dự án portfolio để ứng tuyển chương trình "Nhân tài AI thực chiến" (Vingroup / VinUni)

---

## 1. Tổng quan

### 1.1 Bài toán
Tại cổng ra vào bãi đỗ xe (chung cư, trung tâm thương mại, nhà máy), bảo vệ phải ghi biển số thủ công hoặc dùng thẻ giấy — chậm, dễ sai, khó tra cứu. Dự án xây dựng hệ thống **tự động nhận diện biển số xe Việt Nam từ camera**, ghi nhận lượt vào/ra và cho phép tra cứu lịch sử.

### 1.2 Mục tiêu
1. Phát hiện biển số trong ảnh/video với độ chính xác cao.
2. Đọc đúng **toàn bộ ký tự** biển số, hỗ trợ cả **biển 1 dòng** (ô tô) và **biển 2 dòng** (xe máy, một số ô tô).
3. Chạy **realtime** trên video từ camera/webcam.
4. Có ứng dụng demo hoàn chỉnh: ghi log vào/ra, tra cứu, giao diện web.

### 1.3 Ngoài phạm vi (phiên bản đầu)
- Biển số nước ngoài, biển ngoại giao, biển quân đội (ghi nhận nhưng không tối ưu).
- Ảnh ban đêm không có đèn chiếu / camera hồng ngoại (để dành cho phần mở rộng).
- Nhận diện hãng xe, màu xe.

---

## 2. Yêu cầu

### 2.1 Yêu cầu chức năng

| ID | Chức năng | Mô tả |
|----|-----------|-------|
| F1 | Phát hiện biển số | Nhận ảnh/frame, trả về bounding box các biển số kèm độ tin cậy |
| F2 | Đọc ký tự (OCR) | Đọc chuỗi ký tự từ vùng biển số, hỗ trợ 1 dòng & 2 dòng |
| F3 | Hậu xử lý | Chuẩn hoá & kiểm tra định dạng biển số VN (regex), sửa lỗi ký tự dễ nhầm |
| F4 | Theo dõi đối tượng | Tracking xe qua nhiều frame, bầu chọn (voting) kết quả đọc ổn định nhất |
| F5 | Ghi nhận vào/ra | Lưu biển số, thời gian, ảnh crop, hướng (vào/ra) vào CSDL |
| F6 | API | REST API nhận ảnh → trả kết quả JSON |
| F7 | Giao diện demo | Web: upload ảnh/video, xem stream webcam, bảng lịch sử, tìm kiếm theo biển số |

### 2.2 Yêu cầu phi chức năng — chỉ tiêu mục tiêu

| Chỉ số | Mục tiêu | Ghi chú |
|--------|----------|---------|
| Detection mAP@0.5 | ≥ 0.95 | Trên tập test |
| Detection mAP@0.5:0.95 | ≥ 0.70 | |
| Character accuracy | ≥ 97% | Tỷ lệ ký tự đọc đúng |
| **Plate accuracy (exact match)** | **≥ 90%** | Chỉ số quan trọng nhất — đúng toàn bộ biển |
| FPS end-to-end (GPU) | ≥ 25 FPS | Video 720p |
| FPS end-to-end (CPU, ONNX) | ≥ 8 FPS | Để demo trên laptop không GPU |
| Độ trễ API (1 ảnh) | < 200 ms | GPU |

> Các chỉ tiêu là mục tiêu ban đầu, sẽ điều chỉnh sau khi có baseline (tuần 2).

---

## 3. Định dạng biển số Việt Nam

Hiểu rõ định dạng giúp hậu xử lý tăng mạnh độ chính xác.

| Loại | Ví dụ | Cấu trúc |
|------|-------|----------|
| Ô tô — 1 dòng | `51G-123.45` | 2 số (mã tỉnh) + 1–2 chữ (seri) + 4–5 số |
| Ô tô — 2 dòng | `51G` / `123.45` | Như trên, tách 2 dòng |
| Xe máy — 2 dòng | `59-X1` / `123.45` | Dòng 1: mã tỉnh + seri (chữ + số), dòng 2: 4–5 số |

**Quy tắc hậu xử lý (F3):**
- Chuẩn hoá: bỏ dấu `-`, `.`, khoảng trắng → dạng chuẩn `51G12345`.
- Kiểm tra regex, ví dụ: `^\d{2}[A-Z]{1,2}\d{0,1}\d{4,5}$` (sẽ tinh chỉnh theo dữ liệu thật).
- Sửa lỗi theo vị trí: vị trí bắt buộc là số thì đổi `O→0`, `D→0`, `B→8`, `I→1`, `Z→2`, `S→5`; vị trí bắt buộc là chữ thì đổi ngược lại.
- Kiểm tra mã tỉnh nằm trong danh sách hợp lệ.

---

## 4. Dữ liệu

### 4.1 Nguồn dữ liệu (cần kiểm tra license trước khi dùng)
- Các bộ dữ liệu biển số Việt Nam công khai trên **Roboflow Universe** và **Kaggle** (tìm "vietnamese license plate").
- Bộ dữ liệu **GreenParking** (ảnh bãi đỗ xe máy VN) — cần xác minh nguồn và điều kiện sử dụng.
- **Tự thu thập**: chụp/quay khoảng 300–500 ảnh tại bãi xe thực tế (điện thoại) → đây là điểm cộng lớn trong CV vì chứng minh làm dữ liệu thật.

### 4.2 Gán nhãn
- Công cụ: **Label Studio** hoặc **CVAT** / Roboflow.
- Detection: bounding box lớp `plate` (có thể tách `plate_1line`, `plate_2line`).
- OCR: chuỗi ký tự cho từng ảnh crop biển số.

### 4.3 Chia tập
- Train / Val / Test = 70 / 15 / 15.
- **Tập test giữ riêng hoàn toàn**, ưu tiên chứa ảnh tự thu thập để đánh giá khách quan.
- Thống kê dữ liệu trong README: số ảnh, tỷ lệ 1 dòng / 2 dòng, điều kiện ánh sáng, góc chụp.

### 4.4 Tăng cường dữ liệu
Xoay nhẹ (±10°), perspective, blur, thay đổi độ sáng/tương phản, nhiễu, giả lập mưa/mờ chuyển động.

---

## 5. Kiến trúc hệ thống

```
 Camera / Video / Ảnh
         │
         ▼
 ┌──────────────────┐
 │ 1. Plate Detector│  YOLO (v8/v11) → bounding box biển số
 └────────┬─────────┘
          ▼
 ┌──────────────────┐
 │ 2. Crop & Align  │  cắt vùng biển, chỉnh phối cảnh (perspective transform)
 └────────┬─────────┘
          ▼
 ┌──────────────────┐
 │ 3. Line Split    │  phân loại 1 dòng / 2 dòng (tỷ lệ khung hoặc classifier nhỏ)
 └────────┬─────────┘     → 2 dòng: tách thành 2 ảnh dòng
          ▼
 ┌──────────────────┐
 │ 4. OCR           │  Baseline: PaddleOCR · Nâng cao: CRNN + CTC tự train
 └────────┬─────────┘
          ▼
 ┌──────────────────┐
 │ 5. Post-process  │  chuẩn hoá, regex, sửa lỗi theo vị trí
 └────────┬─────────┘
          ▼
 ┌──────────────────┐
 │ 6. Tracking+Vote │  ByteTrack theo dõi xe; voting kết quả OCR qua nhiều frame
 └────────┬─────────┘
          ▼
 ┌──────────────────┐
 │ 7. App layer     │  FastAPI + SQLite/PostgreSQL + giao diện Streamlit
 └──────────────────┘
```

### 5.1 Lựa chọn mô hình
| Thành phần | Baseline | Phương án nâng cao |
|------------|----------|-------------------|
| Detector | YOLOv8n / YOLO11n pretrained, fine-tune | YOLO bản s/m, so sánh tốc độ–độ chính xác |
| OCR | PaddleOCR pretrained | CRNN (CNN + BiLSTM + CTC) tự train trên crop biển VN |
| Tracking | Không tracking (từng frame) | ByteTrack + voting |
| Tối ưu | PyTorch | Export ONNX (CPU), TensorRT FP16 (GPU) |

> **Ablation study** (so sánh có/không từng thành phần) là phần thể hiện tư duy kỹ sư — nên đưa vào README.

---

## 6. Tech stack

| Mảng | Công cụ |
|------|---------|
| Ngôn ngữ | Python 3.11 |
| Deep learning | PyTorch, Ultralytics (YOLO), PaddleOCR |
| Xử lý ảnh | OpenCV, Albumentations |
| Tracking | ByteTrack (qua `supervision` hoặc Ultralytics) |
| Tối ưu inference | ONNX Runtime, TensorRT (tuỳ phần cứng) |
| Backend | FastAPI, SQLite (dev) / PostgreSQL |
| Frontend demo | Streamlit |
| Theo dõi thí nghiệm | MLflow hoặc Weights & Biases |
| Đóng gói | Docker, docker-compose |
| Chất lượng code | pytest, ruff, GitHub Actions (CI) |
| Train | Google Colab / Kaggle (GPU miễn phí) |

---

## 7. Cấu trúc thư mục dự kiến

```
dl-project/
├── README.md               # giới thiệu, kết quả, demo GIF, hướng dẫn chạy
├── SPEC.md                 # tài liệu này
├── configs/                # file cấu hình train/inference (yaml)
├── data/
│   ├── raw/                # dữ liệu gốc (không commit)
│   ├── processed/          # dữ liệu đã chia train/val/test
│   └── README.md           # mô tả nguồn & thống kê dữ liệu
├── notebooks/              # EDA, thử nghiệm nhanh
├── src/alpr/
│   ├── detection/          # train & inference YOLO
│   ├── ocr/                # PaddleOCR wrapper, CRNN model
│   ├── postprocess/        # chuẩn hoá, regex, sửa lỗi
│   ├── tracking/           # ByteTrack + voting
│   ├── pipeline.py         # ghép toàn bộ pipeline
│   └── export.py           # export ONNX / TensorRT
├── app/
│   ├── api/                # FastAPI
│   ├── db/                 # model CSDL, lịch sử vào/ra
│   └── ui/                 # Streamlit
├── scripts/                # train, evaluate, benchmark FPS
├── tests/                  # unit test (đặc biệt cho postprocess)
├── Dockerfile
└── docker-compose.yml
```

---

## 8. Đánh giá

### 8.1 Phương pháp
- **Detection:** mAP@0.5, mAP@0.5:0.95, Precision, Recall trên tập test.
- **OCR:** Character accuracy, Plate accuracy (exact match), đánh giá riêng 1 dòng vs 2 dòng.
- **End-to-end:** Plate accuracy trên ảnh gốc (detector + OCR + hậu xử lý).
- **Tốc độ:** FPS & latency trên: GPU Colab (T4), CPU laptop — so sánh PyTorch vs ONNX vs TensorRT.

### 8.2 Bảng kết quả mẫu cần có trong README

| Cấu hình | Plate Acc | FPS (GPU) | FPS (CPU) |
|----------|-----------|-----------|-----------|
| YOLO + PaddleOCR | ? | ? | ? |
| + Hậu xử lý regex | ? | ? | ? |
| + CRNN tự train | ? | ? | ? |
| + Tracking & voting (video) | ? | ? | ? |
| + ONNX / TensorRT | ? | ? | ? |

### 8.3 Phân tích lỗi (Error analysis)
Thu thập các ca sai, phân nhóm nguyên nhân (mờ, nghiêng, chói sáng, che khuất, nhầm ký tự) và đề xuất cải thiện. **Phần này nhà tuyển dụng đánh giá rất cao.**

---

## 9. Kế hoạch triển khai (6 tuần)

| Tuần | Công việc | Đầu ra |
|------|-----------|--------|
| 1 | Thu thập & gán nhãn dữ liệu, EDA, setup repo | Dataset v1, `data/README.md` |
| 2 | Fine-tune YOLO detector + baseline PaddleOCR | Baseline end-to-end, số liệu đầu tiên |
| 3 | Xử lý 2 dòng, hậu xử lý regex, unit test | Plate accuracy cải thiện, có test |
| 4 | Train CRNN tự xây, tracking + voting cho video | Bảng ablation |
| 5 | Export ONNX/TensorRT, benchmark; FastAPI + DB + Streamlit | Demo chạy realtime |
| 6 | Docker, CI, error analysis, README, video demo | Repo hoàn chỉnh, sẵn sàng đưa vào CV |

**MVP tối thiểu (nếu gấp, 2–3 tuần):** tuần 1 + 2 + phần hậu xử lý + Streamlit demo ảnh.

---

## 10. Rủi ro & phương án

| Rủi ro | Phương án |
|--------|-----------|
| Thiếu dữ liệu biển 2 dòng | Tự thu thập thêm; sinh ảnh biển số tổng hợp (synthetic) bằng font biển số VN |
| OCR nhầm ký tự tương tự (0/D, 8/B) | Hậu xử lý theo vị trí + regex; tăng dữ liệu cho ký tự hay nhầm |
| Không có GPU | Train trên Colab/Kaggle; inference bằng ONNX trên CPU |
| Ảnh nghiêng, chói, mờ | Augmentation mạnh; perspective transform; voting qua nhiều frame |
| Quyền riêng tư (biển số là dữ liệu cá nhân) | Không công khai dữ liệu tự thu thập có thông tin nhận dạng; làm mờ khi đăng demo |

---

## 11. Sản phẩm bàn giao

- [ ] Repo GitHub public, README có: mô tả, kiến trúc, bảng kết quả, GIF/video demo, hướng dẫn chạy
- [ ] Model weights (Hugging Face Hub hoặc GitHub Release)
- [ ] Demo online (Hugging Face Spaces) hoặc video demo YouTube
- [ ] Docker chạy được bằng 1 lệnh: `docker compose up`
- [ ] Báo cáo ngắn: ablation + error analysis

---

## 12. Mô tả dự án trong CV (mẫu — điền số liệu thật sau khi hoàn thành)

> **Vietnamese License Plate Recognition System** — PyTorch, YOLO, PaddleOCR/CRNN, ONNX, FastAPI, Docker
> - Xây dựng pipeline nhận diện biển số xe VN (1 & 2 dòng) cho cổng bãi đỗ xe, dataset X ảnh trong đó Y ảnh tự thu thập & gán nhãn.
> - Đạt mAP@0.5 = __ cho detection và __% plate accuracy end-to-end; hậu xử lý theo định dạng biển VN tăng độ chính xác thêm __%.
> - Tối ưu bằng ONNX/TensorRT đạt __ FPS, tăng __x so với PyTorch; triển khai API + giao diện web bằng Docker.
> - [GitHub] · [Demo]
