"""Tests for the waitlist rules (no database needed)."""
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.rules.waitlist import first_fit, is_refill, offer_expiry, window
from app.schemas.waitlist import WaitlistJoin

UTC = timezone.utc
T = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)


def test_window_uses_the_business_time_zone():
    start, end = window(date(2026, 11, 13), time(16), time(19), "Asia/Kolkata")
    assert start.astimezone(UTC).hour == 10 and (start.utcoffset(), end - start) == (timedelta(hours=5, minutes=30), timedelta(hours=3))


def test_first_fit_picks_the_earliest_start_inside_the_window():
    starts = [T + timedelta(minutes=m) for m in (-30, 45, 15, 200)]
    assert first_fit(starts, T, T + timedelta(hours=3)) == T + timedelta(minutes=15)
    assert first_fit(starts, T + timedelta(hours=4), T + timedelta(hours=5)) is None


def test_offer_lasts_30_minutes_but_not_too_close_to_the_start():
    assert offer_expiry(T, T + timedelta(hours=5)) == T + timedelta(minutes=30)
    assert offer_expiry(T, T + timedelta(minutes=45)) == T + timedelta(minutes=15)
    assert offer_expiry(T, T + timedelta(minutes=20)) is None


STAFF, OTHER, SLOT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def refill(**changes):
    facts = dict(cancelled_at=T, freed_start=T + timedelta(hours=5), freed_end=T + timedelta(hours=6),
                 freed_staff_id=STAFF, freed_slot_id=None, new_start=T + timedelta(hours=5, minutes=30),
                 new_end=T + timedelta(hours=6, minutes=30), new_staff_id=STAFF, new_slot_id=None,
                 new_created_at=T + timedelta(minutes=10))
    facts.update(changes)
    return is_refill(**facts)


def test_overlapping_new_booking_with_the_same_person_is_a_refill():
    assert refill()


def test_not_a_refill_when():
    assert not refill(new_staff_id=OTHER)                                   # someone else's diary
    assert not refill(new_start=T + timedelta(hours=6), new_end=T + timedelta(hours=7))   # just after, no overlap
    assert not refill(new_created_at=T - timedelta(minutes=1))              # booked before the cancellation


def test_class_seat_refill():
    assert refill(freed_slot_id=SLOT, new_slot_id=SLOT, new_staff_id=None)
    assert not refill(freed_slot_id=SLOT, new_slot_id=uuid.uuid4(), new_staff_id=None)


# ---------- joining the waitlist ----------

def test_join_for_an_appointment_window():
    data = WaitlistJoin(service_ids=[uuid.uuid4()], wanted_date=date(2026, 11, 13),
                        earliest_time=time(16), latest_time=time(19))
    assert data.slot_id is None


def test_join_for_a_full_class():
    assert WaitlistJoin(slot_id=uuid.uuid4()).service_ids == []


@pytest.mark.parametrize("fields", [
    {},                                                                                   # nothing
    {"service_ids": [str(uuid.uuid4())], "wanted_date": "2026-11-13"},                    # no time window
    {"service_ids": [str(uuid.uuid4())], "wanted_date": "2026-11-13",
     "earliest_time": "19:00", "latest_time": "16:00"},                                   # window backwards
    {"slot_id": str(uuid.uuid4()), "wanted_date": "2026-11-13"},                          # class + appointment mixed
])
def test_invalid_waitlist_requests(fields):
    with pytest.raises(ValidationError):
        WaitlistJoin(**fields)