"""Tests for the multi-service booking request (no database needed)."""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.client import BookingCreate

START = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)


def request(**fields):
    base = dict(service_ids=[uuid.uuid4(), uuid.uuid4()], starts_at=START, payment_option="deposit_held")
    base.update(fields)
    return BookingCreate(**base)


def test_valid_request_with_any_staff():
    data = request()
    assert len(data.service_ids) == 2 and data.staff_id is None


def test_specific_staff_member():
    staff = uuid.uuid4()
    assert request(staff_id=staff).staff_id == staff


@pytest.mark.parametrize("fields", [
    {"service_ids": []},                                    # nothing chosen
    {"service_ids": [uuid.uuid4() for _ in range(11)]},    # too many services
    {"starts_at": datetime(2026, 10, 20, 9, 0)},           # no time zone
    {"payment_option": "pay_now"},                          # not offered yet
    {"slot_id": str(uuid.uuid4())},                         # old field no longer accepted
    {"price": "1.00"},                                      # the client never sets the price
])
def test_invalid_requests_are_rejected(fields):
    with pytest.raises(ValidationError):
        request(**fields)