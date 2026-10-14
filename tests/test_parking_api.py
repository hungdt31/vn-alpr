import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from alpr.types import PlateResult
from app.api.main import create_app
from app.db.repository import EventRepository
from app.parking.config import LotConfig, ParkingConfig
from app.parking.lot import ParkingLot


class FakePipeline:
    """Returns whatever plate the test puts in `reads` (text, ocr_conf)."""

    def __init__(self):
        self.reads = [("54L19999", 0.9)]

    def process_image(self, img):
        return [PlateResult((20, 20, 120, 90), 0.9, t, t, c, True, True, [t]) for t, c in self.reads]


@pytest.fixture
def pipeline():
    return FakePipeline()


@pytest.fixture
def client(tmp_path, pipeline):
    repo = EventRepository(tmp_path / "a.db")
    cfg = ParkingConfig(lot=LotConfig(cards=3, slots={"motorbike": 2, "car": 1}), db=str(tmp_path / "a.db"),
                        captures_dir=str(tmp_path / "captures"), allow_time_travel=True)
    lot = ParkingLot(cfg, on_event=lambda *e: repo.add_event(*e, gate="sim"))
    yield TestClient(create_app(pipeline=pipeline, repo=repo, lot=lot))
    lot.close()
    repo.close()


def snapshot():
    img = np.full((120, 160, 3), 200, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    return {"file": ("cam.jpg", buf.tobytes(), "image/jpeg")}


def test_full_visit_with_fee(client, pipeline):
    lot = client.get("/parking/lot").json()
    assert lot["cards"]["next_code"] == "T001" and len(lot["slots"]) == 3

    cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    assert cap["plates"][0]["text"] == "54L19999"
    assert client.get(f"/parking/captures/{cap['id']}/image").headers["content-type"] == "image/jpeg"

    assert client.post("/parking/plates/validate", json={"text": "54-L1 9999"}).json()["valid"]
    s = client.post("/parking/entry", json={"card_id": 1, "plate": "54-L1 9999", "vehicle_type": "motorbike",
                                           "capture_id": cap["id"], "style": {"color": "#ffdc58"}}).json()
    assert s["slot_id"] == "M01" and s["card_code"] == "T001" and not s["edited"]
    assert [e["plate"] for e in client.get("/parked").json()] == ["54L19999"]  # mirrored into the gate log

    client.post("/parking/clock", json={"hours": 5})
    pipeline.reads = [("54L19999", 0.99)]
    out_cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    check = client.post("/parking/exit/check", json={"card_id": 1, "capture_id": out_cap["id"]}).json()
    assert check["match"]["status"] == "ok" and check["fee"] == 7000

    done = client.post("/parking/exit/confirm", json={"session_id": s["id"], "capture_id": out_cap["id"]}).json()
    assert done["status"] == "exited"
    assert client.get("/parking/stats").json()["revenue_total"] == 7000
    assert client.get("/parked").json() == []


def test_mismatch_is_refused_without_guard_reason(client, pipeline):
    cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    s = client.post("/parking/entry", json={"card_id": 1, "plate": "54L19999", "vehicle_type": "motorbike",
                                           "capture_id": cap["id"]}).json()
    pipeline.reads = [("30A12345", 0.99)]
    out_cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    body = {"session_id": s["id"], "capture_id": out_cap["id"]}
    r = client.post("/parking/exit/confirm", json=body)
    assert r.status_code == 409 and "bảo vệ" in r.json()["detail"]
    r = client.post("/parking/exit/confirm", json={**body, "override_reason": "Chủ xe có giấy đăng ký"})
    assert r.status_code == 200


def test_entry_errors_and_lost_card_lookup(client):
    assert client.post("/parking/entry", json={"card_id": 1, "plate": "xyz", "vehicle_type": "car"}).status_code == 422
    assert client.post("/parking/entry", json={"card_id": 1, "plate": "51G-123.45", "vehicle_type": "bus"}
                       ).status_code == 422
    client.post("/parking/entry", json={"card_id": 1, "plate": "51G-123.45", "vehicle_type": "car"})
    r = client.post("/parking/entry", json={"card_id": 2, "plate": "30A-123.45", "vehicle_type": "car"})
    assert r.status_code == 409 and "hết chỗ" in r.json()["detail"]

    cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    check = client.post("/parking/exit/check", json={"plate": "51G12345", "capture_id": cap["id"], "lost_card": True})
    assert check.json()["session"]["card_code"] == "T001" and check.json()["lost_card"]
    assert client.post("/parking/exit/check", json={"capture_id": cap["id"]}).status_code == 422


def test_export_corrections(client, pipeline, tmp_path):
    pipeline.reads = [("54L19998", 0.6)]  # model misread, driver corrects it
    cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    client.post("/parking/entry", json={"card_id": 1, "plate": "54-L1 9999", "vehicle_type": "motorbike",
                                       "capture_id": cap["id"]})
    out = tmp_path / "corr"
    r = client.post("/parking/corrections/export", json={"out": str(out), "edited_only": True}).json()
    assert r["lines"] == 2  # a 2-line plate gives one image per line
    assert (out / "labels.tsv").read_text().split() == ["gate_00000_0.png", "54L1", "gate_00000_1.png", "9999"]
    assert client.get("/parking/stats").json()["ocr_edit_rate"] == 1.0
