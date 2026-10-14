from datetime import timedelta

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from alpr.types import PlateResult
from app.api.main import create_app
from app.container import build_container
from app.core.errors import Invalid
from tests.helpers import T0, make_settings


class FakePipeline:
    def process_image(self, img):
        return [
            PlateResult((10, 10, 100, 40), 0.95, "51G12345", "51G-123.45", 0.9, True, False, ["51G-123.45"]),
            PlateResult((200, 10, 260, 50), 0.6, "5X", "5X", 0.3, False, True, ["5", "X"]),
        ]


@pytest.fixture
def container(tmp_path, clock):
    c = build_container(make_settings(tmp_path), pipeline=FakePipeline(), clock=clock)
    yield c
    c.close()


def test_gate_log_entry_exit_duration_and_parked(container):
    log = container.gate_log
    assert log.record("51G12345", "51G-123.45", "in", 0.9, ts=T0)
    assert log.record("59X112345", "59-X1 123.45", "in", 0.9, ts=T0)
    assert {e.plate for e in log.parked()} == {"51G12345", "59X112345"}

    out = log.record("51G12345", "51G-123.45", "out", 0.9, ts=T0 + timedelta(hours=2))
    assert out.duration_s == 7200
    assert [e.plate for e in log.parked()] == ["59X112345"]
    assert len(log.list(plate="51G")) == 2


def test_gate_log_cooldown_dedup(container):
    log = container.gate_log
    assert log.record("51G12345", "51G-123.45", "in", 0.9, ts=T0)
    assert log.record("51G12345", "51G-123.45", "in", 0.9, ts=T0 + timedelta(seconds=10)) is None
    assert log.record("51G12345", "51G-123.45", "in", 0.9, ts=T0 + timedelta(minutes=5))
    with pytest.raises(Invalid):
        log.record("51G12345", "x", "sideways", 0.9)


@pytest.fixture
def client(container):
    return TestClient(create_app(container))


def jpeg():
    ok, buf = cv2.imencode(".jpg", np.zeros((64, 64, 3), np.uint8))
    return {"file": ("x.jpg", buf.tobytes(), "image/jpeg")}


def test_api_recognize(client):
    r = client.post("/recognize", files=jpeg())
    assert r.status_code == 200
    body = r.json()
    assert [p["display"] for p in body["plates"]] == ["51G-123.45", "5X"]
    assert body["plates"][0]["box"] == [10, 10, 100, 40]
    assert "latency_ms" in body


def test_api_rejects_non_image(client):
    r = client.post("/recognize", files={"file": ("x.txt", b"not an image", "text/plain")})
    assert r.status_code == 400
    assert r.json() == {"detail": "Cannot decode image"}


def test_api_gate_logs_only_valid_plates(client):
    r = client.post("/gate/in", files=jpeg())
    assert [e["plate"] for e in r.json()["events"]] == ["51G12345"]
    assert [e["plate"] for e in client.get("/parked").json()] == ["51G12345"]
    assert len(client.get("/events", params={"plate": "51G-123.45"}).json()) == 1
    assert client.post("/gate/sideways", files=jpeg()).status_code == 422


def test_importing_the_api_opens_nothing():
    """The module-level app builds its container only when a server starts (lifespan)."""
    from app.api import main

    assert main.app.state.container is None


def test_serves_the_built_web_ui_without_hiding_the_api(container, tmp_path):
    web = tmp_path / "dist"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>VN-ALPR</title>")
    client = TestClient(create_app(container, web_dir=str(web)))
    assert "VN-ALPR" in client.get("/").text
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/parking/lot").json()["cards"]["available"] == 4


def test_preload_warms_the_pipeline_at_startup(tmp_path, clock):
    calls = []

    class CountingPipeline(FakePipeline):
        def process_image(self, img):
            calls.append(img.shape)
            return super().process_image(img)

    settings = make_settings(tmp_path)
    settings.preload_pipeline = True
    container = build_container(settings, pipeline=CountingPipeline(), clock=clock)
    with TestClient(create_app(container)):  # entering the client runs the lifespan
        assert calls == [(480, 640, 3)]
    container.close()
