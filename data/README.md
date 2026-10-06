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

## 5. Thống kê (điền sau khi EDA)

| Tập | Ảnh | Biển | 1 dòng | 2 dòng | Ban ngày | Ban đêm |
|-----|-----|------|--------|--------|----------|---------|
| train | | | | | | |
| val | | | | | | |
| test | | | | | | |
