"""Tests for the rules engine.

Each test describes one real situation a business could face. If any of these fail,
money could be captured or released wrongly, so they must all pass before every commit.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.rules.engine import (
    Action,
    BookingFacts,
    Event,
    Fee,
    FeeKind,
    Policy,
    decide,
)

# A fixed appointment time: 20 Oct 2026, 7:00 UTC.
START = datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)
HELD = Decimal("20.00")


def make_policy(**overrides) -> Policy:
    """A typical owner policy. Tests change only the values they care about."""
    values = {
        "version": 1,
        "free_cancel_hours": 24,
        "late_cancel_fee": {"kind": "percent_of_hold", "value": "50"},
        "no_show_fee": {"kind": "percent_of_hold", "value": "100"},
        "waive_if_refilled": True,
        "grace_minutes": 10,
    }
    values.update(overrides)
    return Policy.from_dict(values)


POLICY = make_policy()


def facts(event, *, cancelled_before=None, refilled=False, held=HELD) -> BookingFacts:
    """Build booking facts. cancelled_before = how long before the start the client cancelled."""
    event_time = START - cancelled_before if cancelled_before is not None else None
    return BookingFacts(START, held, event, event_time=event_time, slot_refilled=refilled)


# ---------- attendance, rescheduling, owner actions ----------

def test_attended_captures_held_amount_without_approval():
    d = decide(facts(Event.ATTENDED), POLICY, now=START + timedelta(hours=1))
    assert d.action == Action.CAPTURE
    assert d.amount == HELD
    assert not d.needs_owner_approval


def test_reschedule_keeps_hold():
    d = decide(facts(Event.RESCHEDULED), POLICY, now=START)
    assert d.action == Action.KEEP_HOLD and d.amount == Decimal("0.00")


def test_owner_cancelled_always_voids():
    d = decide(facts(Event.OWNER_CANCELLED), POLICY, now=START)
    assert d.action == Action.VOID and not d.needs_owner_approval


def test_exception_goes_to_owner_with_void_suggested():
    d = decide(facts(Event.EXCEPTION_CLAIMED), POLICY, now=START)
    assert d.action == Action.OWNER_DECIDES
    assert d.suggested_action == Action.VOID
    assert d.needs_owner_approval


# ---------- client cancellations ----------

def test_early_cancellation_is_free():
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=30)), POLICY, now=START)
    assert d.action == Action.VOID and d.rule == "early_cancellation"


def test_cancelling_exactly_at_cutoff_is_free():
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=24)), POLICY, now=START)
    assert d.action == Action.VOID


def test_late_cancellation_charges_half_and_needs_approval():
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=5)), POLICY, now=START)
    assert d.action == Action.CAPTURE
    assert d.amount == Decimal("10.00")
    assert d.needs_owner_approval
    assert d.rule == "late_cancellation"


def test_late_cancellation_waived_when_slot_refilled():
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=5), refilled=True),
               POLICY, now=START)
    assert d.action == Action.VOID and d.rule == "late_cancellation_refilled"


def test_refill_not_waived_if_owner_turned_it_off():
    policy = make_policy(waive_if_refilled=False)
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=5), refilled=True),
               policy, now=START)
    assert d.action == Action.CAPTURE


def test_cancelling_after_start_uses_no_show_fee():
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(minutes=-5)), POLICY, now=START)
    assert d.rule == "no_show" and d.amount == HELD


# ---------- no-shows ----------

def test_no_show_inside_grace_period_waits():
    d = decide(facts(Event.NO_SHOW), POLICY, now=START + timedelta(minutes=5))
    assert d.action == Action.WAIT and d.amount == Decimal("0.00")


def test_no_show_after_grace_captures_full_deposit():
    d = decide(facts(Event.NO_SHOW), POLICY, now=START + timedelta(minutes=11))
    assert d.action == Action.CAPTURE and d.amount == HELD and d.needs_owner_approval


def test_no_show_waived_when_slot_used_by_someone_else():
    d = decide(facts(Event.NO_SHOW, refilled=True), POLICY, now=START + timedelta(minutes=30))
    assert d.action == Action.VOID and d.rule == "no_show_refilled"


# ---------- owner-defined values are respected ----------

def test_owner_48_hour_window_makes_30_hours_a_late_cancellation():
    policy = make_policy(free_cancel_hours=48)
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=30)), policy, now=START)
    assert d.action == Action.CAPTURE and d.amount == Decimal("10.00")


def test_owner_15_minute_grace_period():
    policy = make_policy(grace_minutes=15)
    assert decide(facts(Event.NO_SHOW), policy, now=START + timedelta(minutes=12)).action == Action.WAIT
    assert decide(facts(Event.NO_SHOW), policy, now=START + timedelta(minutes=16)).action == Action.CAPTURE


def test_fixed_fee_larger_than_hold_is_capped():
    policy = make_policy(
        late_cancel_fee={"kind": "fixed", "value": "40"},
        no_show_fee={"kind": "fixed", "value": "80"},
    )
    d = decide(facts(Event.NO_SHOW), policy, now=START + timedelta(hours=1))
    assert d.amount == HELD
    assert d.fee_capped
    assert "limited to the amount held" in d.reason


def test_zero_fee_policy_releases_hold():
    policy = make_policy(late_cancel_fee={"kind": "fixed", "value": "0"})
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=1)), policy, now=START)
    assert d.action == Action.VOID


def test_percentage_fee_rounds_to_cents():
    d = decide(facts(Event.CLIENT_CANCELLED, cancelled_before=timedelta(hours=2), held=Decimal("15.55")),
               POLICY, now=START)
    assert d.amount == Decimal("7.78")


# ---------- policy validation and storage ----------

def test_policy_survives_save_and_load():
    assert Policy.from_dict(POLICY.to_dict()) == POLICY


@pytest.mark.parametrize("overrides, message", [
    ({"free_cancel_hours": -1}, "Free cancellation"),
    ({"free_cancel_hours": 200}, "Free cancellation"),
    ({"grace_minutes": 90}, "Grace period"),
    ({"version": 0}, "version"),
    ({"late_cancel_fee": {"kind": "percent_of_hold", "value": "150"}}, "more than 100%"),
    ({"no_show_fee": {"kind": "fixed", "value": "-5"}}, "negative"),
])
def test_invalid_owner_policies_are_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        make_policy(**overrides)


def test_unknown_fee_kind_is_rejected():
    with pytest.raises(ValueError):
        make_policy(no_show_fee={"kind": "double", "value": "10"})


# ---------- bad input protection ----------

def test_times_without_timezone_are_rejected():
    naive = BookingFacts(datetime(2026, 10, 20, 7, 0), HELD, Event.ATTENDED)
    with pytest.raises(ValueError, match="timezone-aware"):
        decide(naive, POLICY, now=START)


def test_cancellation_requires_event_time():
    with pytest.raises(ValueError, match="event_time"):
        decide(facts(Event.CLIENT_CANCELLED), POLICY, now=START)


def test_negative_held_amount_is_rejected():
    with pytest.raises(ValueError):
        decide(facts(Event.ATTENDED, held=Decimal("-1")), POLICY, now=START)