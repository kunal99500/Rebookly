"""Tests for reminder timing, retry delays, and message wording (no database or email needed)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.notifications.rules import MAX_ATTEMPTS, next_attempt, reminder_due
from app.notifications.templates import KINDS, render

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


@pytest.mark.parametrize("booked_ahead, until_start, expected", [
    (48 * H, 30 * H, None),             # booked 2 days ahead, still 30h to go
    (48 * H, 24 * H, "reminder_24h"),   # now 24h before
    (48 * H, 3 * H, "reminder_24h"),    # job was late: still send the one reminder
    (10 * H, 5 * H, None),              # booked same day, 5h to go
    (10 * H, 2 * H, "reminder_2h"),
    (2 * H, 1 * H, None),               # booked 2h before: the confirmation is enough
    (48 * H, -1 * H, None),             # already started
])
def test_reminder_timing(booked_ahead, until_start, expected):
    starts_at = NOW + until_start
    assert reminder_due(starts_at=starts_at, booked_at=starts_at - booked_ahead, now=NOW) == expected


def test_retries_wait_longer_each_time_then_stop():
    waits = [next_attempt(n, NOW) - NOW for n in range(1, MAX_ATTEMPTS)]
    assert waits == sorted(waits) and waits[0] == timedelta(minutes=1)
    assert next_attempt(MAX_ATTEMPTS, NOW) is None


PAYLOAD = {"business_name": "Ravi's <Barbershop>", "visit": "Haircut + Hair wash", "when": "Tue 20 Oct, 9:00 AM",
           "held": "₹80.00", "policy_line": "Free cancellation up to 24 hours before.", "ref": "RB-AAAA-BBBB",
           "client_name": "Priya", "amount": "₹40.00", "released": "₹40.00", "reason": "Cancelled late.",
           "by": "by you", "outcome": "Your hold was released.", "error": "Authorization expired", "code": "123456",
           "link": "https://rebookly.app/my"}


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_renders(kind):
    subject, text, html = render(kind, PAYLOAD)
    assert subject and text.endswith("— Rebookly") and html.startswith("<div")


def test_confirmation_says_held_not_charged():
    _, text, _ = render("booking_confirmed", PAYLOAD)
    assert "₹80.00 is held" in text and "isn't charged" in text and "RB-AAAA-BBBB" in text


def test_html_is_escaped():
    _, _, html = render("booking_confirmed", PAYLOAD)
    assert "&lt;Barbershop&gt;" in html and "<Barbershop>" not in html


def test_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        render("party_invitation", PAYLOAD)