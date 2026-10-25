"""Tests for the pure rules around booking outcomes."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.rules.engine import Action, Decision
from app.rules.outcomes import can_check_in, initial_status, masked_last4, payment_status_after_capture

START = datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=1)


@pytest.mark.parametrize("offset, allowed", [
    (timedelta(minutes=-61), False),   # too early
    (timedelta(minutes=-60), True),    # check-in opens
    (timedelta(minutes=30), True),     # during the session
    (timedelta(hours=3), True),        # two hours after the end
    (timedelta(hours=3, minutes=1), False),
])
def test_check_in_window(offset, allowed):
    assert can_check_in(START, END, START + offset) is allowed


def decision(action, needs_approval):
    return Decision(action, Decimal("10"), needs_approval, "rule", "reason")


@pytest.mark.parametrize("action, needs_approval, expected", [
    (Action.CAPTURE, True, "pending_approval"),     # a fee
    (Action.CAPTURE, False, "approved"),            # attended: deposit applied to the price
    (Action.VOID, False, "approved"),               # free cancellation
    (Action.OWNER_DECIDES, True, "pending_approval"),
])
def test_initial_status(action, needs_approval, expected):
    assert initial_status(decision(action, needs_approval)) == expected


def test_payment_status_after_capture():
    assert payment_status_after_capture(Decimal("20"), Decimal("20")) == "captured"
    assert payment_status_after_capture(Decimal("20"), Decimal("10")) == "partially_captured"


def test_masked_phone():
    assert masked_last4("3456") == "•••• 3456"
    assert masked_last4(None) is None