"""Tests for document contents: which document, its number, and every amount printed on it."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.documents.snapshots import amounts, build_snapshot, document_number, document_type_for
from app.rules.formatting import money

D = Decimal


@pytest.mark.parametrize("event, action, amount, expected", [
    ("attended", "capture", D("20"), "payment_receipt"),
    ("client_cancelled", "capture", D("10"), "fee_receipt"),
    ("no_show", "capture", D("20"), "fee_receipt"),
    ("client_cancelled", "capture", D("0"), "release_notice"),   # owner waived the fee
    ("client_cancelled", "void", None, "release_notice"),        # free cancellation
    ("owner_cancelled", "void", D("0"), "release_notice"),
])
def test_document_type_for(event, action, amount, expected):
    assert document_type_for(event, action, amount) == expected


def test_document_numbers():
    assert document_number("RB-7K2M-9QXD", "booking_confirmation", 1) == "RB-7K2M-9QXD-C1"
    assert document_number("RB-7K2M-9QXD", "fee_receipt", 2) == "RB-7K2M-9QXD-F2"


@pytest.mark.parametrize("doc_type, charged, expected", [
    ("booking_confirmation", D("0"), {"charged": D("0"), "held": D("20"), "released": D("0"), "due_after": D("25")}),
    ("payment_receipt", D("20"), {"charged": D("20"), "held": D("0"), "released": D("0"), "due_after": D("25")}),
    ("fee_receipt", D("10"), {"charged": D("10"), "held": D("0"), "released": D("10"), "due_after": D("0")}),
    ("release_notice", D("0"), {"charged": D("0"), "held": D("0"), "released": D("20"), "due_after": D("0")}),
])
def test_amounts_always_add_up(doc_type, charged, expected):
    result = amounts(doc_type, price=D("45"), held=D("20"), charged=charged)
    assert result == expected


def test_full_amount_held_receipt_has_nothing_due_after():
    assert amounts("payment_receipt", price=D("45"), held=D("45"), charged=D("45"))["due_after"] == D("0")


def test_money_formatting():
    assert money(D("1234.5"), "USD") == "$1,234.50"
    assert money("20", "INR") == "₹20.00"
    assert money(D("7"), "CHF") == "7.00 CHF"


def snapshot(doc_type, charged=D("0")):
    return build_snapshot(
        doc_type, number="RB-AAAA-BBBB-C1",
        issued_at=datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc), issued_local="Mon 19 Oct, 1:30 PM",
        business={"name": "Lumen Fitness", "address": None, "phone": None, "timezone": "Asia/Kolkata"},
        client={"name": "Priya", "phone_masked": "+44 •••• ••3456", "attendee": None},
        booking={"confirmation_number": "RB-AAAA-BBBB", "service": "1:1 session", "duration_minutes": 60,
                 "when": "Tue 20 Oct, 7:00 AM", "payment_option": "deposit_held", "price": "45.00",
                 "held": "20.00", "currency": "USD", "check_in_token": "tok-123"},
        payment={"method": "card", "card_brand": "VISA", "card_last_digits": "4242", "paypal_order_id": "5O1"},
        policy={"version": 2, "lines": ["Free cancellation up to 24 hours before."], "free_until": "Mon 19 Oct, 7:00 AM"},
        charged=charged,
        decision={"reason": "Cancelled late.", "rule": "late_cancellation"} if doc_type == "fee_receipt" else None,
    )


def test_confirmation_snapshot_says_held_not_charged_and_has_qr_token():
    snap = snapshot("booking_confirmation")
    assert snap["title"] == "Booking confirmation"
    assert snap["money"]["held"] == "$20.00" and snap["money"]["charged"] == "$0.00"
    assert snap["check_in_token"] == "tok-123"


def test_fee_receipt_snapshot_has_reason_and_no_qr_token():
    snap = snapshot("fee_receipt", charged=D("10"))
    assert snap["money"]["charged"] == "$10.00" and snap["money"]["released"] == "$10.00"
    assert snap["decision"]["rule"] == "late_cancellation"
    assert "check_in_token" not in snap


def test_snapshot_never_contains_full_phone_numbers():
    assert "7911" not in str(snapshot("booking_confirmation"))