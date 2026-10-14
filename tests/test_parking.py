from datetime import datetime, timedelta

import pytest

from app.parking.config import FeeConfig, LotConfig, MatchConfig, ParkingConfig, load_parking_config
from app.parking.lot import ParkingError, ParkingLot
from app.parking.rules import match_exit_plate, parking_fee, parse_plate_input

T0 = datetime(2026, 10, 14, 8, 0, 0)


def test_parking_yaml_loads():
    cfg = load_parking_config("configs/parking.yaml")
    assert sum(cfg.lot.slots.values()) == 30
    assert set(cfg.fees) == {"motorbike", "car"}


def test_fee_base_then_per_started_hour():
    fee = FeeConfig(base=5000, base_hours=4, per_hour=2000, lost_card=50000)
    assert parking_fee(fee, T0, T0 + timedelta(minutes=5)) == 5000
    assert parking_fee(fee, T0, T0 + timedelta(hours=4)) == 5000
    assert parking_fee(fee, T0, T0 + timedelta(hours=4, minutes=1)) == 7000  # a started hour counts
    assert parking_fee(fee, T0, T0 + timedelta(hours=6)) == 9000
    assert parking_fee(fee, T0, T0 + timedelta(hours=1), lost_card=True) == 55000


def test_plate_input_accepts_space_or_slash_between_lines():
    for text in ("54-L1 9999", "54-L1/9999", "54L19999"):
        assert parse_plate_input(text).text == "54L19999"
    assert parse_plate_input("51G-123.45").display == "51G-123.45"
    assert not parse_plate_input("hello").valid


@pytest.mark.parametrize(
    "reads, status",
    [
        ([("54L19999", 0.99)], "ok"),
        ([("54-L1 9999", 0.99)], "ok"),  # formatting does not matter
        ([("5HL19999", 0.70)], "suspect"),  # one char off, unsure model: likely a misread
        ([("54L19998", 0.99)], "mismatch"),  # one char off but the model is sure: another vehicle
        ([("30A12345", 0.99)], "mismatch"),
        ([], "suspect"),  # nothing read at the exit: a guard has to look
        ([("30A12345", 0.99), ("54L19999", 0.9)], "ok"),  # several plates in view: the closest one counts
    ],
)
def test_exit_match(reads, status):
    assert match_exit_plate("54L19999", reads, MatchConfig(1, 0.95)).status == status


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def lot(tmp_path, clock):
    cfg = ParkingConfig(lot=LotConfig(cards=4, slots={"motorbike": 2, "car": 1}), db=str(tmp_path / "p.db"),
                        captures_dir=str(tmp_path / "captures"), allow_time_travel=True)
    events = []
    lot = ParkingLot(cfg, now=clock, on_event=lambda *e: events.append(e))
    lot.events = events
    yield lot
    lot.close()


def capture(lot, text, conf=0.9, box=(10, 10, 100, 40)):
    plates = [{"box": list(box), "text": text, "ocr_conf": conf, "valid": True}] if text else []
    return lot.save_capture(b"jpeg-bytes", plates)["id"]


def test_entry_assigns_card_slot_and_flags_corrections(lot):
    state = lot.state()
    assert state["cards"]["available"] == 4 and state["cards"]["next_code"] == "T001"

    s1 = lot.enter(1, "54-L1 9999", "motorbike", capture(lot, "54L19999"))
    assert (s1["card_code"], s1["slot_id"], s1["plate"], s1["edited"]) == ("T001", "M01", "54L19999", False)

    s2 = lot.enter(2, "51G-123.45", "car", capture(lot, "51G12346"), style={"model": "sedan", "color": "#e63946"})
    assert s2["edited"] and s2["plate_ocr"] == "51G12346"  # driver fixed the model's read
    assert s2["vehicle_style"]["color"] == "#e63946"

    state = lot.state()
    assert state["cards"] == {**state["cards"], "available": 2, "in_use": 2, "next": 3}
    assert state["capacity"]["car"]["free"] == 0
    assert [e[2] for e in lot.events] == ["in", "in"]
    assert lot.stats()["ocr_edit_rate"] == 0.5


def test_entry_refusals(lot):
    lot.enter(1, "54-L1 9999", "motorbike")
    with pytest.raises(ParkingError, match="đang ở trong bãi"):
        lot.enter(2, "54L19999", "motorbike")  # same vehicle twice
    with pytest.raises(ParkingError, match="không có trong thùng"):
        lot.enter(1, "59-X1 123.45", "motorbike")  # ticket already handed out
    with pytest.raises(ParkingError) as e:
        lot.enter(2, "hello", "motorbike")
    assert e.value.status_code == 422
    lot.enter(2, "30A-123.45", "car")
    with pytest.raises(ParkingError, match="hết chỗ cho ô tô"):
        lot.enter(3, "30A-999.99", "car")


def test_exit_ok_returns_ticket_to_bottom_of_dispenser(lot, clock):
    s = lot.enter(1, "54-L1 9999", "motorbike", capture(lot, "54L19999"))
    clock.t = T0 + timedelta(hours=5)
    session = lot.find_parked(card_id=1)
    check = lot.check_exit(session["id"], capture(lot, "54L19999", 0.99))
    assert check["match"]["status"] == "ok"
    assert check["fee"] == 5000 + 2000 and check["duration_s"] == 5 * 3600

    done = lot.confirm_exit(s["id"], check["capture"]["id"])
    assert done["status"] == "exited" and done["fee"] == 7000
    assert lot.state()["cards"]["next"] == 2  # the returned card goes under the others
    assert lot.stats()["today"]["revenue"] == 7000
    with pytest.raises(ParkingError):
        lot.find_parked(card_id=1)


def test_exit_mismatch_needs_guard_reason(lot):
    s = lot.enter(1, "54-L1 9999", "motorbike")
    wrong = capture(lot, "30A12345", 0.99)
    assert lot.check_exit(s["id"], wrong)["match"]["status"] == "mismatch"
    with pytest.raises(ParkingError, match="bảo vệ"):
        lot.confirm_exit(s["id"], wrong)
    done = lot.confirm_exit(s["id"], wrong, override_reason="Đã kiểm tra giấy tờ xe")
    assert done["exit_match"] == "mismatch" and done["override_reason"] == "Đã kiểm tra giấy tờ xe"
    assert lot.stats()["overrides"] == 1


def test_lost_card_locks_ticket_and_charges(lot, clock):
    s = lot.enter(1, "51G-123.45", "car")
    clock.t = T0 + timedelta(hours=1)
    session = lot.find_parked(plate="51G-123.45")
    check = lot.check_exit(session["id"], capture(lot, "51G12345", 0.99), lost_card=True)
    assert check["fee"] == 30000 + 200000
    lot.confirm_exit(s["id"], check["capture"]["id"], lost_card=True)
    assert lot.state()["cards"]["locked"] == 1 and lot.state()["cards"]["locked_ids"] == [1]
    with pytest.raises(ParkingError):
        lot.enter(1, "51G-999.99", "car")  # the lost ticket cannot be used again
    lot.restore_card(1)
    assert lot.state()["cards"]["locked"] == 0


def test_time_travel_and_labeled_captures(lot):
    before = lot.now()
    assert lot.travel(3) == before + timedelta(hours=3)
    lot.enter(1, "51G-123.45", "car", capture(lot, "51G12346"))
    lot.enter(2, "54-L1 9999", "motorbike", capture(lot, "54L19999"))
    assert {c["plate"] for c in lot.labeled_captures()} == {"51G12345", "54L19999"}
    assert [c["plate"] for c in lot.labeled_captures(edited_only=True)] == ["51G12345"]
