from datetime import datetime, timedelta

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from alpr.types import PlateResult
from app.api.main import create_app
from app.db.repository import EventRepository


@pytest.fixture
def repo(tmp_path):
    r = EventRepository(tmp_path / "test.db", cooldown_s=60)
    yield r
    r.close()


def test_repository_entry_exit_duration_and_parked(repo):
    t0 = datetime(2026, 10, 6, 8, 0, 0)
    assert repo.add_event("51G12345", "51G-123.45", "in", 0.9, ts=t0)
    assert repo.add_event("59X112345", "59-X1 123.45", "in", 0.9, ts=t0)
    assert {e["plate"] for e in repo.parked()} == {"51G12345", "59X112345"}

    out = repo.add_event("51G12345", "51G-123.45", "out", 0.9, ts=t0 + timedelta(hours=2))
    assert out["duration_s"] == 7200
    assert [e["plate"] for e in repo.parked()] == ["59X112345"]
    assert len(repo.list_events(plate="51G")) == 2


def test_repository_cooldown_dedup(repo):
    t0 = datetime(2026, 10, 6, 8, 0, 0)
    assert repo.add_event("51G12345", "51G-123.45", "in", 0.9, ts=t0)
    assert repo.add_event("51G12345", "51G-123.45", "in", 0.9, ts=t0 + timedelta(seconds=10)) is None
    assert repo.add_event("51G12345", "51G-123.45", "in", 0.9, ts=t0 + timedelta(minutes=5))
    with pytest.raises(ValueError):
        repo.add_event("51G12345", "x", "sideways", 0.9)


class FakePipeline:
    def process_image(self, img):
        return [
            PlateResult((10, 10, 100, 40), 0.95, "51G12345", "51G-123.45", 0.9, True, False, ["51G-123.45"]),
            PlateResult((200, 10, 260, 50), 0.6, "5X", "5X", 0.3, False, True, ["5", "X"]),
        ]


@pytest.fixture
def client(repo):
    return TestClient(create_app(pipeline=FakePipeline(), repo=repo))


def jpeg():
    ok, buf = cv2.imencode(".jpg", np.zeros((64, 64, 3), np.uint8))
    return {"file": ("x.jpg", buf.tobytes(), "image/jpeg")}


def test_api_recognize(client):
    r = client.post("/recognize", files=jpeg())
    assert r.status_code == 200
    body = r.json()
    assert [p["display"] for p in body["plates"]] == ["51G-123.45", "5X"]
    assert "latency_ms" in body


def test_api_rejects_non_image(client):
    r = client.post("/recognize", files={"file": ("x.txt", b"not an image", "text/plain")})
    assert r.status_code == 400


def test_api_gate_logs_only_valid_plates(client):
    r = client.post("/gate/in", files=jpeg())
    assert [e["plate"] for e in r.json()["events"]] == ["51G12345"]
    assert [e["plate"] for e in client.get("/parked").json()] == ["51G12345"]
    assert len(client.get("/events", params={"plate": "51G-123.45"}).json()) == 1
    assert client.post("/gate/sideways", files=jpeg()).status_code == 422
