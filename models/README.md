# models/

Trained weights (not committed — publish them on Hugging Face Hub or a GitHub Release):

```
models/
├── detector/best.pt      # scripts/train_detector.py   (+ best.onnx / best.engine after export)
└── crnn/best.pt          # scripts/train_crnn.py       (+ best.onnx + best.json after export)
```

Paths are set in `configs/pipeline.yaml`.
