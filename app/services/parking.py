"""Parking lot use cases.

Entry:  save_capture() -> the driver checks/edits the plate -> state().cards.next -> enter()
Exit:   save_capture() -> find_parked() -> check_exit() (ticket plate vs plate read now, fee) -> confirm_exit()
The exit plate is never typed by the driver: a mismatch needs a guard's override reason.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from alpr.metrics import levenshtein
from alpr.postprocess.plate_format import normalize
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.settings import ParkingSettings
from app.domain.matching import PlateMatch, match_exit_plate, parse_plate_input
from app.domain.models import VEHICLE_LABEL, VEHICLE_TYPES, Capture, Session, Slot, card_code
from app.domain.pricing import Tariff, parking_fee
from app.infra.db import Database
from app.infra.image_store import ImageStore
from app.infra.repositories.captures import CaptureRepository
from app.infra.repositories.cards import CardRepository
from app.infra.repositories.sessions import SessionRepository
from app.infra.repositories.slots import SlotRepository
from app.services.gate_log import GateLog
from app.services.ports import Clock


# ---- views returned to the API ---------------------------------------------------------------
@dataclass
class CardsSummary:
    available: int
    in_use: int
    locked: int
    locked_ids: list[int]
    next: int | None  # top of the dispenser
    next_code: str | None


@dataclass
class Capacity:
    total: int
    free: int


@dataclass
class SlotView:
    id: str
    vehicle_type: str
    session: Session | None


@dataclass
class LotState:
    name: str
    now: datetime
    time_offset_h: float
    allow_time_travel: bool
    cards: CardsSummary
    capacity: dict[str, Capacity]
    slots: list[SlotView]
    fees: dict[str, Tariff]


@dataclass
class ExitCheck:
    session: Session
    capture: Capture
    match: PlateMatch
    fee: int
    lost_card: bool
    exit_time: datetime
    duration_s: int


@dataclass
class DayTotals:
    entries: int
    exits: int
    revenue: int


@dataclass
class Stats:
    parked: dict[str, int]
    today: DayTotals
    revenue_total: int
    entries_total: int
    ocr_edit_rate: float | None  # share of plates drivers had to correct: a field estimate of the OCR error rate
    corrections: int
    overrides: int
    lost_cards: int


class ParkingService:
    def __init__(self, db: Database, cards: CardRepository, slots: SlotRepository, sessions: SessionRepository,
                 captures: CaptureRepository, images: ImageStore, clock: Clock, settings: ParkingSettings,
                 gate_log: GateLog | None = None):
        """gate_log: entries and exits are also written to the gate log, so /events and /parked include them."""
        self.db = db
        self.cards = cards
        self.slots = slots
        self.sessions = sessions
        self.captures = captures
        self.images = images
        self.clock = clock
        self.settings = settings
        self.gate_log = gate_log

    def setup(self) -> None:
        """Create the tickets and slots of the configured layout (idempotent)."""
        with self.db.transaction():
            self.cards.seed(self.settings.lot.cards)
            self.slots.seed(self.settings.lot.slots)

    # ---- clock ------------------------------------------------------------------------------
    def now(self) -> datetime:
        return self.clock.now()

    def travel(self, hours: float) -> datetime:
        """Demo only: move the clock forward so fees for long stays can be shown."""
        if not self.settings.allow_time_travel or not hasattr(self.clock, "advance"):
            raise Forbidden("Tua thời gian đang bị tắt (allow_time_travel: false)")
        try:
            return self.clock.advance(hours)
        except ValueError as e:
            raise Invalid(str(e)) from e

    # ---- captures ---------------------------------------------------------------------------
    def save_capture(self, jpeg: bytes, plates: list[dict]) -> Capture:
        """Keep the camera image and what the model read, as evidence for the guard and for retraining."""
        with self.db.transaction():
            capture_id = self.captures.add(plates, self.now())
            self.captures.set_path(capture_id, self.images.save(capture_id, jpeg))
        return self.get_capture(capture_id)

    def get_capture(self, capture_id: int) -> Capture:
        capture = self.captures.get(capture_id)
        if capture is None:
            raise NotFound(f"Không có ảnh chụp #{capture_id}")
        return capture

    # ---- lot state --------------------------------------------------------------------------
    def state(self) -> LotState:
        by_slot = {s.slot_id: s for s in self.sessions.parked()}
        slots = [SlotView(s.id, s.vehicle_type, by_slot.get(s.id)) for s in self.slots.all()]
        counts = self.cards.count_by_status()
        nxt = self.cards.next_available()
        offset = getattr(self.clock, "offset", None)
        return LotState(
            name=self.settings.lot.name,
            now=self.now(),
            time_offset_h=offset.total_seconds() / 3600 if offset is not None else 0.0,
            allow_time_travel=self.settings.allow_time_travel,
            cards=CardsSummary(
                available=counts.get("available", 0), in_use=counts.get("in_use", 0),
                locked=counts.get("locked", 0), locked_ids=self.cards.locked_ids(),
                next=nxt.id if nxt else None, next_code=nxt.code if nxt else None,
            ),
            capacity={
                kind: Capacity(total=n, free=sum(1 for s in slots if s.vehicle_type == kind and s.session is None))
                for kind, n in self.settings.lot.slots.items()
            },
            slots=slots,
            fees=self.settings.fees,
        )

    # ---- entry ------------------------------------------------------------------------------
    def enter(self, card_id: int, plate_text: str, vehicle_type: str, capture_id: int | None = None,
              style: dict | None = None) -> Session:
        if vehicle_type not in VEHICLE_TYPES:
            raise Invalid(f"Loại xe không hợp lệ: {vehicle_type}")
        plate = parse_plate_input(plate_text)
        if not plate.valid:
            raise Invalid(f"'{plate_text}' không đúng định dạng biển số Việt Nam")

        ocr_text, ocr_conf, box = "", 0.0, None
        if capture_id is not None:
            reads = self.get_capture(capture_id).plates
            if reads:  # the plate the driver confirmed: the read closest to the final text
                best = min(reads, key=lambda p: levenshtein(normalize(p["text"]), plate.text))
                ocr_text, ocr_conf, box = normalize(best["text"]), float(best["ocr_conf"]), list(best["box"])

        with self.db.transaction():
            if self.sessions.parked_with_plate(plate.text):
                raise Conflict(f"Xe {plate.display} đang ở trong bãi, không thể gửi thêm lần nữa")
            card = self.cards.get(card_id)
            if card is None or card.status != "available":
                raise Conflict(f"Thẻ {card_code(card_id)} không có trong thùng")
            slot: Slot | None = self.slots.first_free(vehicle_type)
            if slot is None:
                raise Conflict(f"Bãi đã hết chỗ cho {VEHICLE_LABEL[vehicle_type]}")
            session_id = self.sessions.add(Session(
                id=0, card_id=card_id, slot_id=slot.id, vehicle_type=vehicle_type, plate=plate.text,
                display=plate.display, entry_time=self.now(), vehicle_style=style or {}, plate_ocr=ocr_text,
                ocr_conf=ocr_conf, edited=ocr_text != plate.text,  # typed from scratch counts as a correction too
                entry_capture=capture_id, entry_box=box,
            ))
            self.cards.set_status(card_id, "in_use")
            if self.gate_log:
                self.gate_log.record(plate.text, plate.display, "in", ocr_conf, gate="sim")
        return self.get_session(session_id)

    # ---- exit -------------------------------------------------------------------------------
    def find_parked(self, card_id: int | None = None, plate: str | None = None) -> Session:
        if card_id is not None:
            session = self.sessions.parked_with_card(card_id)
            if session is None:
                raise NotFound(f"Thẻ {card_code(card_id)} không gắn với xe nào trong bãi")
            return session
        if not plate:
            raise Invalid("Cần mã thẻ, hoặc biển số khi mất thẻ")
        session = self.sessions.parked_with_plate(normalize(plate))
        if session is None:
            raise NotFound(f"Không có xe {plate} trong bãi")
        return session

    def check_exit(self, session_id: int, capture_id: int, lost_card: bool = False) -> ExitCheck:
        """What the exit gate shows: plate on the ticket vs plate read now, and the fee. Changes nothing."""
        session = self.get_session(session_id)
        if session.status != "parked":
            raise Conflict("Xe này đã ra khỏi bãi")
        capture = self.get_capture(capture_id)
        match = match_exit_plate(session.plate, [(p["text"], p["ocr_conf"]) for p in capture.plates],
                                 self.settings.matching)
        now = self.now()
        fee = parking_fee(self.settings.fees[session.vehicle_type], session.entry_time, now, lost_card)
        # never negative: an entry made while the demo clock was fast-forwarded can lie "in the future"
        duration_s = max(0, int((now - session.entry_time).total_seconds()))
        return ExitCheck(session=session, capture=capture, match=match, fee=fee, lost_card=lost_card,
                         exit_time=now, duration_s=duration_s)

    def confirm_exit(self, session_id: int, capture_id: int, lost_card: bool = False,
                     override_reason: str | None = None) -> Session:
        check = self.check_exit(session_id, capture_id, lost_card)
        reason = (override_reason or "").strip() or None
        if check.match.status != "ok" and not reason:
            raise Conflict("Biển số lúc ra không khớp với thẻ: bảo vệ phải kiểm tra và ghi lý do cho xe ra")
        done = replace(check.session, status="exited", exit_capture=capture_id, exit_plate_ocr=check.match.read,
                       exit_match=check.match.status, exit_time=check.exit_time, fee=check.fee,
                       lost_card=lost_card, override_reason=reason)
        with self.db.transaction():
            self.sessions.save_exit(done)
            if lost_card:  # the missing ticket must never open the gate again
                self.cards.set_status(done.card_id, "locked")
            else:
                self.cards.set_status(done.card_id, "available", returned_at=check.exit_time)
            if self.gate_log:
                self.gate_log.record(done.plate, done.display, "out", 1.0, gate="sim")
        return self.get_session(session_id)

    def restore_card(self, card_id: int) -> CardsSummary:
        """A lost ticket was found (or replaced): put it back in the dispenser."""
        with self.db.transaction():
            card = self.cards.get(card_id)
            if card is None or card.status != "locked":
                raise NotFound(f"Thẻ {card_code(card_id)} không ở trạng thái bị khoá")
            self.cards.set_status(card_id, "available", returned_at=self.now())
        return self.state().cards

    # ---- sessions & stats -------------------------------------------------------------------
    def get_session(self, session_id: int) -> Session:
        session = self.sessions.get(session_id)
        if session is None:
            raise NotFound(f"Không có lượt gửi #{session_id}")
        return session

    def list_sessions(self, status: str | None = None, plate: str | None = None, limit: int = 100) -> list[Session]:
        return self.sessions.list(status, normalize(plate) if plate else None, limit)

    def stats(self) -> Stats:
        totals = self.sessions.totals()
        today = self.sessions.day_totals(self.now().date())
        return Stats(
            parked={kind: self.sessions.count_parked(kind) for kind in self.settings.lot.slots},
            today=DayTotals(**today),
            revenue_total=totals["revenue"],
            entries_total=totals["entries"],
            ocr_edit_rate=totals["corrections"] / totals["with_photo"] if totals["with_photo"] else None,
            corrections=totals["corrections"],
            overrides=totals["overrides"],
            lost_cards=len(self.cards.locked_ids()),
        )

    def labeled_entries(self, edited_only: bool = False) -> list[dict]:
        """Entry photos with the plate the driver confirmed: free training labels for the OCR model."""
        return self.sessions.labeled_entries(edited_only)
