"""Tests for opening-hours input and slot bookability (no database needed)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.schedule import AvailabilityIn
from app.services.schedule import is_bookable

NOW = datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc)


def test_valid_weekly_hours_are_accepted():
    data = AvailabilityIn(hours=[
        {"weekday": 0, "start": "07:00", "end": "12:00"},
        {"weekday": 0, "start": "16:00", "end": "20:00"},
        {"weekday": 5, "start": "08:00", "end": "11:30"},
    ])
    assert len(data.hours) == 3


@pytest.mark.parametrize("hours", [
    [{"weekday": 7, "start": "09:00", "end": "12:00"}],                    # no 8th day
    [{"weekday": 0, "start": "12:00", "end": "09:00"}],                    # closes before opening
    [{"weekday": 0, "start": "09:00", "end": "09:00"}],                    # zero length
    [{"weekday": 0, "start": "09:00:30", "end": "12:00"}],                 # seconds not allowed
    [{"weekday": 0, "start": "09:00", "end": "13:00"},
     {"weekday": 0, "start": "12:00", "end": "17:00"}],                    # overlap
])
def test_invalid_hours_are_rejected(hours):
    with pytest.raises(ValidationError):
        AvailabilityIn(hours=hours)


def test_empty_hours_mean_closed_all_week():
    assert AvailabilityIn(hours=[]).hours == []


def slot(**fields):
    base = dict(is_blocked=False, booked_count=0, capacity=1, starts_at=NOW + timedelta(hours=5))
    base.update(fields)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("fields, expected", [
    ({}, True),
    ({"is_blocked": True}, False),
    ({"booked_count": 1}, False),
    ({"starts_at": NOW - timedelta(minutes=1)}, False),           # already started
    ({"starts_at": NOW + timedelta(hours=73)}, False),            # beyond the 72-hour window
    ({"starts_at": NOW + timedelta(hours=72)}, True),             # exactly at the edge
    ({"capacity": 5, "booked_count": 4}, True),                   # group class with a seat left
])
def test_bookability(fields, expected):
    assert is_bookable(slot(**fields), NOW) is expected


# ---------- provider can't be double-booked ----------

from types import SimpleNamespace  # noqa: E402

from app.rules.scheduling import BusyPeriod, remove_busy  # noqa: E402

T9 = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)


def make_slot(slot_id, start_minutes, length_minutes):
    start = T9 + timedelta(minutes=start_minutes)
    return SimpleNamespace(id=slot_id, starts_at=start, ends_at=start + timedelta(minutes=length_minutes))


def test_overlapping_slot_of_another_service_is_hidden():
    hour_slot = make_slot("A", 0, 60)            # 9:00-10:00, booked
    half_hour_slots = [make_slot("B1", 0, 30), make_slot("B2", 30, 30), make_slot("B3", 60, 30)]
    busy = [BusyPeriod("A", hour_slot.starts_at, hour_slot.ends_at)]
    assert [s.id for s in remove_busy(half_hour_slots, busy)] == ["B3"]


def test_slot_touching_a_booking_is_still_free():
    busy = [BusyPeriod("A", T9, T9 + timedelta(minutes=60))]
    assert [s.id for s in remove_busy([make_slot("B", 60, 30)], busy)] == ["B"]


def test_booking_in_the_same_slot_does_not_hide_it():
    group_class = make_slot("C", 0, 60)
    busy = [BusyPeriod("C", group_class.starts_at, group_class.ends_at)]
    assert remove_busy([group_class], busy) == [group_class]