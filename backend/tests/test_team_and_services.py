"""Tests for team input rules and the new service options (no database needed)."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.service import ServiceCreate, ServiceUpdate
from app.schemas.team import StaffCreate, StaffUpdate, TimeOffIn

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)


# ---------- services: add-ons, cleanup, booking mode ----------

def test_add_on_without_deposit_is_allowed():
    wash = ServiceCreate(name="Hair wash", kind="add_on", duration_minutes=15, price="5", deposit="0")
    assert wash.kind == "add_on" and wash.booking_mode == "appointment"


def test_main_service_still_needs_a_deposit_for_deposit_option():
    with pytest.raises(ValidationError):
        ServiceCreate(name="Haircut", duration_minutes=30, price="20", deposit="0")


def test_cleanup_time_is_limited():
    assert ServiceCreate(name="Colour", duration_minutes=90, cleanup_minutes=10, price="60", deposit="15").cleanup_minutes == 10
    with pytest.raises(ValidationError):
        ServiceCreate(name="Colour", duration_minutes=90, cleanup_minutes=300, price="60", deposit="15")


@pytest.mark.parametrize("field, value", [("kind", "extra"), ("booking_mode", "drop_in")])
def test_unknown_kind_or_mode_is_rejected(field, value):
    with pytest.raises(ValidationError):
        ServiceCreate(name="Haircut", duration_minutes=30, price="20", deposit="5", **{field: value})


def test_service_update_cannot_blank_kind():
    with pytest.raises(ValidationError):
        ServiceUpdate(kind=None)


# ---------- staff ----------

def test_new_staff_without_services_offers_everything():
    assert StaffCreate(name="Ben").service_ids is None


@pytest.mark.parametrize("fields", [{"name": None}, {"is_active": None}, {"service_ids": None}])
def test_staff_update_cannot_blank_fields(fields):
    with pytest.raises(ValidationError):
        StaffUpdate(**fields)


# ---------- time off ----------

def test_valid_time_off():
    off = TimeOffIn(starts_at=NOW, ends_at=NOW + timedelta(hours=1), reason="Lunch")
    assert off.staff_id is None   # whole business


@pytest.mark.parametrize("start, end", [
    (NOW, NOW),                                     # zero length
    (NOW, NOW - timedelta(hours=1)),                # ends before it starts
    (NOW, NOW + timedelta(days=63)),                # too long in one go
])
def test_invalid_time_off_is_rejected(start, end):
    with pytest.raises(ValidationError):
        TimeOffIn(starts_at=start, ends_at=end)


def test_time_off_needs_time_zones():
    with pytest.raises(ValidationError):
        TimeOffIn(starts_at=datetime(2026, 10, 19, 9), ends_at=datetime(2026, 10, 19, 10))