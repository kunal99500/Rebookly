"""Tests for the plain-language policy summary shown to clients."""
from app.rules.policy_text import policy_summary
from app.rules.engine import Policy

BASE = {
    "version": 1,
    "free_cancel_hours": 24,
    "late_cancel_fee": {"kind": "percent_of_hold", "value": "50"},
    "no_show_fee": {"kind": "percent_of_hold", "value": "100"},
    "waive_if_refilled": True,
    "grace_minutes": 10,
}


def summary(**changes):
    return policy_summary(Policy.from_dict({**BASE, **changes}))


def test_typical_policy():
    assert summary() == [
        "Free cancellation up to 24 hours before your appointment.",
        "Cancelling later: 50% of your hold may be kept.",
        "Missing your appointment: your full hold may be kept.",
        "No fee if someone else takes your slot.",
        "Running up to 10 minutes late is fine.",
    ]


def test_fixed_fee_and_singular_hour():
    lines = summary(free_cancel_hours=1, late_cancel_fee={"kind": "fixed", "value": "15"})
    assert lines[0] == "Free cancellation up to 1 hour before your appointment."
    assert lines[1] == "Cancelling later: up to 15.00 of your hold may be kept."


def test_no_free_window():
    assert summary(free_cancel_hours=0)[0] == "Cancelling: 50% of your hold may be kept."


def test_completely_free_policy_has_no_refill_line():
    lines = summary(late_cancel_fee={"kind": "fixed", "value": "0"}, no_show_fee={"kind": "fixed", "value": "0"})
    assert "Cancelling later is also free." in lines
    assert "No charge if you miss your appointment." in lines
    assert not any("someone else" in line for line in lines)


def test_no_grace_period_line_when_zero():
    assert not any("late is fine" in line for line in summary(grace_minutes=0))


def test_refill_line_hidden_when_owner_disabled_it():
    assert not any("someone else" in line for line in summary(waive_if_refilled=False))