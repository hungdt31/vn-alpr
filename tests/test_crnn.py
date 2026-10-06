import numpy as np
import pytest

torch = pytest.importorskip("torch")

from alpr.ocr.crnn.charset import Charset  # noqa: E402
from alpr.ocr.crnn.model import CRNN, prepare_line  # noqa: E402
from alpr.ocr.crnn.recognizer import CRNNRecognizer  # noqa: E402


def test_charset_roundtrip_and_greedy_decode():
    cs = Charset()
    ids = cs.encode("51G12345")
    assert len(ids) == 8 and Charset.BLANK not in ids
    # path: 5 5 blank 1 G G blank 1 -> "51G1"
    path = [cs.encode("5")[0]] * 2 + [0] + cs.encode("1G") + cs.encode("G") + [0] + cs.encode("1")
    probs = np.zeros((len(path), 1, cs.num_classes), np.float32)
    probs[np.arange(len(path)), 0, path] = 1.0
    assert cs.decode_greedy(probs) == [("51G1", 1.0)]


def test_prepare_line_shape_and_range():
    x = prepare_line(np.full((40, 300, 3), 255, np.uint8))
    assert x.shape == (1, 32, 128) and x.dtype == np.float32
    assert x.min() >= -1 and x.max() <= 1


def test_crnn_output_shape():
    model = CRNN(Charset().num_classes).eval()
    out = model(torch.zeros(2, 1, 32, 128))
    assert out.shape == (32, 2, Charset().num_classes)


def test_recognizer_loads_checkpoint(tmp_path):
    cs = Charset()
    meta = {"chars": cs.chars, "img_h": 32, "img_w": 128, "hidden": 64}
    model = CRNN(cs.num_classes, hidden=64)
    path = tmp_path / "crnn.pt"
    torch.save({"model": model.state_dict(), "meta": meta}, path)

    rec = CRNNRecognizer(path)
    out = rec.recognize([np.zeros((30, 120, 3), np.uint8), np.zeros((50, 60), np.uint8)])
    assert len(out) == 2
    assert all(isinstance(t, str) and 0.0 <= c <= 1.0 for t, c in out)


def test_onnx_export_matches_torch_with_dynamic_batch(tmp_path):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("onnx")
    import contextlib
    import io

    from alpr.export import export_crnn

    cs = Charset()
    meta = {"chars": cs.chars, "img_h": 32, "img_w": 128, "hidden": 64}
    torch.manual_seed(0)
    path = tmp_path / "crnn.pt"
    torch.save({"model": CRNN(cs.num_classes, hidden=64).state_dict(), "meta": meta}, path)
    with contextlib.redirect_stderr(io.StringIO()):
        onnx_path = export_crnn(path)
    assert onnx_path.with_suffix(".json").exists()

    rng = np.random.default_rng(0)
    imgs = [rng.integers(0, 255, (30, 110), dtype=np.uint8) for _ in range(5)]
    torch_rec, onnx_rec = CRNNRecognizer(path), CRNNRecognizer(onnx_path)
    assert onnx_rec.backend == "onnx"
    assert [t for t, _ in torch_rec.recognize(imgs)] == [t for t, _ in onnx_rec.recognize(imgs)]
    assert len(onnx_rec.recognize(imgs[:1])) == 1


def test_crnn_overfits_tiny_synthetic_set():
    """Sanity check that model + CTC + decoding are wired correctly."""
    from alpr.synth import render_plate

    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    cs = Charset()
    texts = ["51G12345", "30A67890"]
    x = torch.from_numpy(np.stack([prepare_line(render_plate([t], rng)) for t in texts]))
    targets = torch.tensor([i for t in texts for i in cs.encode(t)])
    lengths = torch.tensor([len(t) for t in texts])

    model = CRNN(cs.num_classes, hidden=64)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    ctc = torch.nn.CTCLoss(zero_infinity=True)
    for _ in range(500):
        log_probs = model(x).log_softmax(2)
        loss = ctc(log_probs, targets, torch.full((2,), log_probs.size(0)), lengths)
        opt.zero_grad()
        loss.backward()
        opt.step()
        if loss.item() < 0.02:
            break

    # BatchNorm running stats from 2 images are meaningless: keep batch stats, only disable dropout
    for m in model.modules():
        if isinstance(m, (torch.nn.Dropout2d, torch.nn.LSTM)):
            m.eval()
    with torch.no_grad():
        decoded = cs.decode_greedy(model(x).softmax(2).numpy())
    assert [t for t, _ in decoded] == texts
