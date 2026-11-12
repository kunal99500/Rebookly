"""Tests for the group class booking request (no database needed)."""
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.client import ClassBookingCreate


def test_valid_class_booking_request():
    data = ClassBookingCreate(
        slot_id=uuid.uuid4(), payment_option="deposit_held", attendee_name="Asha",
        name="Asha", email="asha@example.com",
    )
    assert data.attendee_name == "Asha"


@pytest.mark.parametrize("fields", [
    {"payment_option": "deposit_held"},                                           # no session chosen
    {"slot_id": str(uuid.uuid4()), "payment_option": "pay_now"},                  # not offered
    {"slot_id": str(uuid.uuid4()), "payment_option": "deposit_held", "seats": 3}, # one seat per booking
    {"slot_id": str(uuid.uuid4()), "payment_option": "deposit_held", "price": "1"},  # client never sets price
    {"slot_id": str(uuid.uuid4()), "payment_option": "deposit_held", "name": "Asha", "email": "invalid"},
])
def test_invalid_class_booking_requests_are_rejected(fields):
    with pytest.raises(ValidationError):
        ClassBookingCreate(**fields)