"""Tests for small booking rules and signed checkout links."""
import re
import uuid
from decimal import Decimal

import pytest

from app.rules.booking import hold_amount, new_check_in_token, new_confirmation_number
from app.security.links import checkout_signature, verify_checkout_signature

SECRET = "s" * 40


def test_deposit_option_holds_the_deposit():
    assert hold_amount(Decimal("45"), Decimal("20"), "deposit_held") == Decimal("20")


def test_full_option_holds_the_price():
    assert hold_amount(Decimal("45"), Decimal("20"), "full_held") == Decimal("45")


def test_unknown_option_is_refused():
    with pytest.raises(ValueError):
        hold_amount(Decimal("45"), Decimal("20"), "pay_now")


def test_confirmation_numbers_are_readable_and_unique():
    numbers = {new_confirmation_number() for _ in range(500)}
    assert len(numbers) == 500
    assert all(re.fullmatch(r"RB-[A-HJ-KM-NP-Z2-9]{4}-[A-HJ-KM-NP-Z2-9]{4}", n) for n in numbers)


def test_check_in_tokens_are_long_and_unique():
    tokens = {new_check_in_token() for _ in range(100)}
    assert len(tokens) == 100 and all(len(t) >= 40 for t in tokens)


def test_checkout_signature_verifies_for_the_right_booking():
    booking_id = uuid.uuid4()
    assert verify_checkout_signature(SECRET, booking_id, checkout_signature(SECRET, booking_id))


def test_checkout_signature_fails_for_another_booking_or_secret():
    booking_id = uuid.uuid4()
    signature = checkout_signature(SECRET, booking_id)
    assert not verify_checkout_signature(SECRET, uuid.uuid4(), signature)
    assert not verify_checkout_signature("t" * 40, booking_id, signature)
    assert not verify_checkout_signature(SECRET, booking_id, "")