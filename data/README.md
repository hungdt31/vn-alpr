# Dữ liệu

> Không commit ảnh lên GitHub. Biển số là dữ liệu cá nhân: ảnh tự chụp chỉ dùng nội bộ, làm mờ khi đăng demo.

## 1. Cấu trúc thư mục

```
data/
├── raw/
│   ├── images/          # ảnh gốc: public datasets + ảnh tự chụp (đặt tên bắt đầu bằng own_)
│   ├── labels/          # nhãn YOLO, cùng tên với ảnh: "0 cx cy w h" (chuẩn hoá 0-1)
│   ├── texts.csv        # chữ trên biển, dùng tạo dữ liệu OCR
│   └── test_texts.csv   # ground truth cho đánh giá end-to-end (tập test)
├── processed/
│   ├── detection/       # do scripts/split_dataset.py tạo
│   └── ocr/{train,val,test}/  # do scripts/make_ocr_crops.py tạo
└── synthetic/ocr/       # do scripts/gen_synthetic.py tạo
```

## 2. Định dạng file nhãn chữ

`texts.csv`: mỗi dòng là một biển. `plate_idx` là thứ tự dòng của box trong file nhãn YOLO, đánh số từ 0.
Biển 2 dòng thì phân tách hai dòng bằng `/`.

```csv
image,plate_idx,text
0001.jpg,0,51G-123.45
0002.jpg,0,59-X1/123.45
0002.jpg,1,30A/999.99
```

`test_texts.csv` dùng cho `scripts/evaluate.py`:

```csv
image,text
own_0001.jpg,59-X1/123.45
```

## 3. Nguồn dữ liệu

Kiểm tra license từng nguồn trước khi dùng, rồi ghi lại vào bảng dưới.

| Nguồn | Số ảnh | 1 dòng / 2 dòng | License | Ghi chú |
|-------|--------|-----------------|---------|---------|
| Roboflow Universe, tìm "vietnamese license plate" | | | | |
| Kaggle, tìm "vietnam license plate" | | | | |
| Tự chụp (`own_*`) | | | Nội bộ | Chỉ đưa vào tập test |

## 4. Gán nhãn

- **Box:** dùng Label Studio, CVAT hoặc Roboflow, export định dạng YOLO, chỉ 1 lớp `plate`.
- **Chữ:** gõ vào `texts.csv`. Nên tạo nhãn cho ảnh tự chụp trước, vì đó là phần quý nhất của dataset.

### Gán nhãn chữ bán tự động

Gõ tay chữ cho hàng nghìn biển rất lâu, nên có thể cho OCR đọc nháp trước rồi người sửa lại:

1. `python scripts/draft_texts.py --ocr paddle --limit test=300 --limit val=300 --limit train=2000`: PaddleOCR đọc nháp các khung có sẵn trong nhãn YOLO, ghi ra `data/drafts/drafts.csv` và ảnh crop. Trên Colab, chạy ô 4b-1 của notebook.
2. `streamlit run scripts/review_texts.py`: xem từng trang ảnh crop, sửa chữ sai, đánh dấu "Bỏ" với biển không đọc được, rồi bấm "Lưu trang". Tiến độ được lưu ngay vào `drafts.csv`, nên có thể dừng lúc nào cũng được.
3. Bấm **Xuất** để có `texts.csv` và `test_texts.csv`:
   - `texts.csv` gồm các biển đã duyệt. Có thể bật pseudo-label để lấy thêm nhãn nháp chưa duyệt của **tập train** khi OCR rất tự tin.
   - `test_texts.csv` chỉ gồm ảnh test mà mọi biển trong ảnh đều đã được duyệt, để biển chưa có nhãn không bị tính là lỗi.

Nên duyệt tập test **kỹ nhất**, vì mọi số liệu đánh giá dựa vào nó. Nếu chỉ giữ nguyên những gì PaddleOCR đọc mà không sửa, bảng so sánh sẽ thiên vị PaddleOCR.

## 5. Thống kê (điền sau khi EDA)

| Tập | Ảnh | Biển | 1 dòng | 2 dòng | Ban ngày | Ban đêm |
|-----|-----|------|--------|--------|----------|---------|
| train | | | | | | |
| val | | | | | | |
| test | | | | | | |
