import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from alpr.types import PlateResult
from app.api.main import create_app
from app.container import build_container
from tests.helpers import make_settings


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
def client(tmp_path, pipeline, clock):
    container = build_container(make_settings(tmp_path, cards=3), pipeline=pipeline, clock=clock)
    yield TestClient(create_app(container))
    container.close()


def snapshot():
    img = np.full((120, 160, 3), 200, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    return {"file": ("cam.jpg", buf.tobytes(), "image/jpeg")}


def test_full_visit_with_fee(client, pipeline):
    lot = client.get("/parking/lot").json()
    assert lot["cards"]["next_code"] == "T001" and len(lot["slots"]) == 3
    assert lot["fees"]["car"]["base"] == 30000 and lot["now"] == "2026-10-14T08:00:00"

    cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    assert cap["plates"][0]["text"] == "54L19999" and "path" not in cap
    assert client.get(f"/parking/captures/{cap['id']}/image").headers["content-type"] == "image/jpeg"

    assert client.post("/parking/plates/validate", json={"text": "54-L1 9999"}).json()["valid"]
    s = client.post("/parking/entry", json={"card_id": 1, "plate": "54-L1 9999", "vehicle_type": "motorbike",
                                           "capture_id": cap["id"], "style": {"color": "#ffdc58"}}).json()
    assert s["slot_id"] == "M01" and s["card_code"] == "T001" and not s["edited"]
    assert client.get("/parking/lot").json()["slots"][0]["session"]["card_code"] == "T001"
    assert [e["plate"] for e in client.get("/parked").json()] == ["54L19999"]  # mirrored into the gate log

    assert client.post("/parking/clock", json={"hours": 5}).json()["now"] == "2026-10-14T13:00:00"
    pipeline.reads = [("54L19999", 0.99)]
    out_cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    check = client.post("/parking/exit/check", json={"card_id": 1, "capture_id": out_cap["id"]}).json()
    assert check["match"]["status"] == "ok" and check["fee"] == 7000

    done = client.post("/parking/exit/confirm", json={"session_id": s["id"], "capture_id": out_cap["id"]}).json()
    assert done["status"] == "exited"
    assert client.get("/parking/stats").json()["revenue_total"] == 7000
    assert client.get("/parked").json() == []
    assert [x["status"] for x in client.get("/parking/sessions").json()] == ["exited"]


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


def test_errors_map_to_http_status(client):
    assert client.post("/parking/entry", json={"card_id": 1, "plate": "xyz", "vehicle_type": "car"}).status_code == 422
    assert client.post("/parking/entry", json={"card_id": 1, "plate": "51G-123.45", "vehicle_type": "bus"}
                       ).status_code == 422
    client.post("/parking/entry", json={"card_id": 1, "plate": "51G-123.45", "vehicle_type": "car"})
    r = client.post("/parking/entry", json={"card_id": 2, "plate": "30A-123.45", "vehicle_type": "car"})
    assert r.status_code == 409 and "hết chỗ" in r.json()["detail"]
    assert client.get("/parking/captures/999/image").status_code == 404
    assert client.post("/parking/cards/2/restore").status_code == 404

    cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    check = client.post("/parking/exit/check", json={"plate": "51G12345", "capture_id": cap["id"], "lost_card": True})
    assert check.json()["session"]["card_code"] == "T001" and check.json()["lost_card"]
    assert client.post("/parking/exit/check", json={"capture_id": cap["id"]}).status_code == 422


def test_export_corrections(client, pipeline, tmp_path):
    pipeline.reads = [("54L19998", 0.6)]  # model misread, driver corrects it
    cap = client.post("/parking/captures", files=snapshot()).json()["capture"]
    client.post("/parking/entry", json={"card_id": 1, "plate": "54-L1 9999", "vehicle_type": "motorbike",
                                       "capture_id": cap["id"]})
    out = tmp_path / "corr"  # exports_dir of the test settings
    r = client.post("/parking/corrections/export", json={"out": "/etc", "edited_only": True}).json()
    assert r["out"] == str(out)  # a path sent by the caller is ignored
    assert r["lines"] == 2  # a 2-line plate gives one image per line
    assert (out / "labels.tsv").read_text().split() == ["gate_00000_0.png", "54L1", "gate_00000_1.png", "9999"]
    assert client.get("/parking/stats").json()["ocr_edit_rate"] == 1.0
