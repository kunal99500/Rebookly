"""Tests for turning weekly hours into bookable slots."""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.rules.scheduling import WeeklyHours, check_no_overlaps, generate_slot_times

MONDAY = date(2026, 10, 19)
LONG_AGO = datetime(2000, 1, 1, tzinfo=timezone.utc)


def test_back_to_back_slots_inside_opening_hours():
    hours = [WeeklyHours(0, time(9, 0), time(12, 0))]
    slots = generate_slot_times(hours, 60, "UTC", MONDAY, 1, LONG_AGO)
    assert [s.starts_at.hour for s in slots] == [9, 10, 11]
    assert all(s.ends_at - s.starts_at == timedelta(hours=1) for s in slots)


def test_slot_that_would_overrun_closing_time_is_skipped():
    hours = [WeeklyHours(0, time(9, 0), time(11, 30))]
    slots = generate_slot_times(hours, 60, "UTC", MONDAY, 1, LONG_AGO)
    assert [s.starts_at.hour for s in slots] == [9, 10]


def test_only_matching_weekdays_get_slots():
    hours = [WeeklyHours(2, time(9, 0), time(10, 0))]  # Wednesday only
    slots = generate_slot_times(hours, 60, "UTC", MONDAY, 7, LONG_AGO)
    assert len(slots) == 1 and slots[0].starts_at.date() == date(2026, 10, 21)


def test_local_time_is_converted_to_utc():
    hours = [WeeklyHours(0, time(9, 0), time(10, 0))]
    slots = generate_slot_times(hours, 60, "Asia/Kolkata", MONDAY, 1, LONG_AGO)
    assert slots[0].starts_at == datetime(2026, 10, 19, 3, 30, tzinfo=timezone.utc)  # 09:00 IST


def test_daylight_saving_change_keeps_local_opening_time():
    # UK clocks go back on Sunday 25 Oct 2026; 09:00 London is 08:00 UTC before and 09:00 UTC after.
    hours = [WeeklyHours(5, time(9, 0), time(10, 0)), WeeklyHours(0, time(9, 0), time(10, 0))]
    slots = generate_slot_times(hours, 60, "Europe/London", date(2026, 10, 24), 3, LONG_AGO)
    assert [s.starts_at.hour for s in slots] == [8, 9]


def test_past_slots_are_skipped():
    hours = [WeeklyHours(0, time(9, 0), time(12, 0))]
    now = datetime(2026, 10, 19, 10, 30, tzinfo=timezone.utc)
    slots = generate_slot_times(hours, 60, "UTC", MONDAY, 1, now)
    assert [s.starts_at.hour for s in slots] == [11]


def test_two_periods_in_one_day():
    hours = [WeeklyHours(0, time(9, 0), time(11, 0)), WeeklyHours(0, time(14, 0), time(15, 0))]
    slots = generate_slot_times(hours, 60, "UTC", MONDAY, 1, LONG_AGO)
    assert [s.starts_at.hour for s in slots] == [9, 10, 14]


def test_overlapping_periods_are_rejected():
    with pytest.raises(ValueError):
        check_no_overlaps([WeeklyHours(0, time(9, 0), time(13, 0)), WeeklyHours(0, time(12, 0), time(17, 0))])


def test_touching_periods_are_allowed():
    check_no_overlaps([WeeklyHours(0, time(9, 0), time(12, 0)), WeeklyHours(0, time(12, 0), time(17, 0))])


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        generate_slot_times([], 60, "UTC", MONDAY, 1, datetime(2026, 1, 1))