"""Tests for when a booking may be moved to another time."""
from datetime import datetime, timedelta, timezone

import pytest

from app.rules.rescheduling import reschedule_problem

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=48)
HONOR_END = NOW + timedelta(hours=60)


def problem(new_start, *, now=NOW, start=START, free_hours=24, honor=HONOR_END):
    return reschedule_problem(now=now, current_start=start, new_start=new_start,
                              free_cancel_hours=free_hours, honor_period_ends_at=honor)


def test_moving_well_before_the_cutoff_is_allowed():
    assert problem(START + timedelta(hours=2)) is None
    assert problem(START - timedelta(hours=20)) is None     # earlier is fine too


def test_moving_inside_the_late_window_is_refused():
    late_now = START - timedelta(hours=5)
    assert "too close" in problem(START + timedelta(hours=1), now=late_now)


def test_exactly_at_the_cutoff_is_refused():
    assert "too close" in problem(START + timedelta(hours=1), now=START - timedelta(hours=24))


def test_no_free_window_means_moves_are_allowed_until_the_start():
    assert problem(START + timedelta(hours=1), free_hours=0, now=START - timedelta(minutes=30)) is None


def test_new_time_beyond_the_hold_window_is_refused():
    assert "too far ahead" in problem(HONOR_END + timedelta(minutes=15))


@pytest.mark.parametrize("new_start, message", [
    (START, "already have"),
    (NOW - timedelta(minutes=1), "future"),
])
def test_pointless_or_past_moves_are_refused(new_start, message):
    assert message in problem(new_start)