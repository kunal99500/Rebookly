"""The rules engine decides what happens to a booking's held money.

Pure functions only: no database, no PayPal, no AI, no reading the system clock.
The AI may *explain* a decision, but only this module *makes* it.

Every policy value is chosen by the business owner. Every fee is capped at the
amount actually held, because PayPal cannot capture more than was authorized.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

MAX_FREE_CANCEL_HOURS = 168   # 7 days
MAX_GRACE_MINUTES = 60


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


# ---------- inputs ----------

class Event(str, Enum):
    ATTENDED = "attended"                    # checked in by QR or confirmed by owner
    CLIENT_CANCELLED = "client_cancelled"
    RESCHEDULED = "rescheduled"              # moved within policy
    NO_SHOW = "no_show"                      # owner reports the client didn't come
    OWNER_CANCELLED = "owner_cancelled"
    EXCEPTION_CLAIMED = "exception_claimed"  # e.g. client reports an emergency


class FeeKind(str, Enum):
    PERCENT_OF_HOLD = "percent_of_hold"
    FIXED = "fixed"


@dataclass(frozen=True)
class Fee:
    kind: FeeKind
    value: Decimal

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("A fee can't be negative")
        if self.kind == FeeKind.PERCENT_OF_HOLD and self.value > 100:
            raise ValueError("A percentage fee can't be more than 100%")

    def amount_for(self, held: Decimal) -> Decimal:
        if self.kind == FeeKind.PERCENT_OF_HOLD:
            return _round(held * self.value / Decimal(100))
        return _round(self.value)

    @classmethod
    def from_dict(cls, data: dict) -> Fee:
        return cls(kind=FeeKind(data["kind"]), value=Decimal(str(data["value"])))

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "value": str(self.value)}


@dataclass(frozen=True)
class Policy:
    """A business's cancellation policy. Every value is chosen by the business owner.

    Created from the owner's confirmed settings (stored in the database as JSON),
    never invented by the AI. Bookings keep the version they were made under.
    """
    free_cancel_hours: int        # cancel at least this many hours before = no fee
    late_cancel_fee: Fee          # fee for cancelling inside that window
    no_show_fee: Fee              # fee when the client doesn't come
    waive_if_refilled: bool       # no fee if someone else books the slot
    grace_minutes: int            # how late a client can be before it counts as a no-show
    version: int                  # which saved version of the owner's policy this is

    def __post_init__(self) -> None:
        if not 0 <= self.free_cancel_hours <= MAX_FREE_CANCEL_HOURS:
            raise ValueError(f"Free cancellation must be between 0 and {MAX_FREE_CANCEL_HOURS} hours")
        if not 0 <= self.grace_minutes <= MAX_GRACE_MINUTES:
            raise ValueError(f"Grace period must be between 0 and {MAX_GRACE_MINUTES} minutes")
        if self.version < 1:
            raise ValueError("Policy version must be 1 or higher")

    @classmethod
    def from_dict(cls, data: dict) -> Policy:
        """Build a Policy from the JSON saved in the database."""
        return cls(
            free_cancel_hours=int(data["free_cancel_hours"]),
            late_cancel_fee=Fee.from_dict(data["late_cancel_fee"]),
            no_show_fee=Fee.from_dict(data["no_show_fee"]),
            waive_if_refilled=bool(data["waive_if_refilled"]),
            grace_minutes=int(data["grace_minutes"]),
            version=int(data["version"]),
        )

    def to_dict(self) -> dict:
        """Turn the Policy into JSON for saving in the database."""
        return {
            "version": self.version,
            "free_cancel_hours": self.free_cancel_hours,
            "late_cancel_fee": self.late_cancel_fee.to_dict(),
            "no_show_fee": self.no_show_fee.to_dict(),
            "waive_if_refilled": self.waive_if_refilled,
            "grace_minutes": self.grace_minutes,
        }


@dataclass(frozen=True)
class BookingFacts:
    appointment_start: datetime
    held_amount: Decimal
    event: Event
    event_time: datetime | None = None  # when the client cancelled; ignored for other events
    slot_refilled: bool = False         # True only once a replacement booking's hold succeeded


# ---------- output ----------

class Action(str, Enum):
    CAPTURE = "capture"
    VOID = "void"
    KEEP_HOLD = "keep_hold"
    WAIT = "wait"                    # too early to decide (e.g. still inside grace period)
    OWNER_DECIDES = "owner_decides"


@dataclass(frozen=True)
class Decision:
    action: Action
    amount: Decimal                 # amount to capture; 0 for void / keep / wait
    needs_owner_approval: bool
    rule: str                       # stable key, used on receipts and in the event log
    reason: str                     # plain-language explanation, generated here, not by AI
    fee_capped: bool = False        # True if the policy fee exceeded the held amount
    suggested_action: Action | None = None  # for OWNER_DECIDES


# ---------- helpers ----------

def _require_aware(dt: datetime, name: str) -> None:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _fee_decision(fee: Fee, held: Decimal, rule: str, label: str) -> Decision:
    computed = fee.amount_for(held)
    amount = min(computed, held)
    capped = computed > held
    if amount <= ZERO:
        return Decision(Action.VOID, ZERO, False, f"{rule}_no_fee",
                        f"{label}, but the policy sets no fee. The hold is released.")
    reason = f"{label}. Under the agreed policy, {amount} of the {held} held is kept."
    if capped:
        reason += f" The policy fee was {computed}, limited to the amount held."
    return Decision(Action.CAPTURE, amount, True, rule, reason, fee_capped=capped)


# ---------- the decision ----------

def decide(facts: BookingFacts, policy: Policy, now: datetime) -> Decision:
    """Return what should happen to the held money for this booking event."""
    _require_aware(facts.appointment_start, "appointment_start")
    _require_aware(now, "now")
    held = _round(facts.held_amount)
    if held < ZERO:
        raise ValueError("held_amount cannot be negative")

    event = facts.event

    if event == Event.OWNER_CANCELLED:
        return Decision(Action.VOID, ZERO, False, "owner_cancelled",
                        "The business cancelled this booking. The hold is released and nothing is charged.")

    if event == Event.ATTENDED:
        return Decision(Action.CAPTURE, held, False, "attended",
                        f"Service completed. The {held} held is applied to the price.")

    if event == Event.RESCHEDULED:
        return Decision(Action.KEEP_HOLD, ZERO, False, "rescheduled",
                        "Booking moved to a new time within the policy. The hold stays in place; nothing is charged.")

    if event == Event.EXCEPTION_CLAIMED:
        return Decision(Action.OWNER_DECIDES, ZERO, True, "exception_claimed",
                        "The client reported exceptional circumstances. The owner decides whether a fee applies.",
                        suggested_action=Action.VOID)

    if event == Event.CLIENT_CANCELLED:
        if facts.event_time is None:
            raise ValueError("event_time is required for a client cancellation")
        _require_aware(facts.event_time, "event_time")
        notice = facts.appointment_start - facts.event_time

        if notice >= timedelta(hours=policy.free_cancel_hours):
            return Decision(Action.VOID, ZERO, False, "early_cancellation",
                            f"Cancelled at least {policy.free_cancel_hours} hours before. "
                            "The hold is released and nothing is charged.")

        if facts.slot_refilled and policy.waive_if_refilled:
            return Decision(Action.VOID, ZERO, False, "late_cancellation_refilled",
                            "Cancelled late, but the slot was booked by someone else. "
                            "The fee is waived and the hold is released.")

        if notice <= timedelta(0):
            return _fee_decision(policy.no_show_fee, held, "no_show", "Cancelled after the start time")

        return _fee_decision(policy.late_cancel_fee, held, "late_cancellation",
                             f"Cancelled less than {policy.free_cancel_hours} hours before")

    if event == Event.NO_SHOW:
        grace_end = facts.appointment_start + timedelta(minutes=policy.grace_minutes)
        if now < grace_end:
            return Decision(Action.WAIT, ZERO, False, "within_grace_period",
                            f"Still within the {policy.grace_minutes}-minute grace period. "
                            "A no-show can't be recorded yet.")
        if facts.slot_refilled and policy.waive_if_refilled:
            return Decision(Action.VOID, ZERO, False, "no_show_refilled",
                            "The slot was used by someone else. The fee is waived and the hold is released.")
        return _fee_decision(policy.no_show_fee, held, "no_show", "The client did not attend")

    raise ValueError(f"Unhandled event: {event}")