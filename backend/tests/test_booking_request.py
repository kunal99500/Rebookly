"""Tests for the multi-service booking request (no database needed)."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.client.bookings import _require_booking_email
from app.schemas.client import BookingCreate

START = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)


def request(**fields):
    base = dict(service_ids=[uuid.uuid4(), uuid.uuid4()], starts_at=START, payment_option="deposit_held",
                name="Asha", email="asha@example.com")
    base.update(fields)
    return BookingCreate(**base)


def test_valid_request_with_any_staff():
    data = request()
    assert len(data.service_ids) == 2 and data.staff_id is None


def test_specific_staff_member():
    staff = uuid.uuid4()
    assert request(staff_id=staff).staff_id == staff


def test_email_is_normalized():
    assert request(email=" ASHA@Example.COM ").email == "asha@example.com"


def test_booking_api_requires_an_email_for_the_confirmation():
    with pytest.raises(HTTPException) as error:
        _require_booking_email(None)
    assert error.value.status_code == 422


@pytest.mark.parametrize("fields", [
    {"service_ids": []},                                    # nothing chosen
    {"service_ids": [uuid.uuid4() for _ in range(11)]},    # too many services
    {"starts_at": datetime(2026, 10, 20, 9, 0)},           # no time zone
    {"payment_option": "pay_now"},                          # not offered yet
    {"slot_id": str(uuid.uuid4())},                         # old field no longer accepted
    {"price": "1.00"},                                      # the client never sets the price
    {"email": "not-an-email"},
])
def test_invalid_requests_are_rejected(fields):
    with pytest.raises(ValidationError):
        request(**fields)