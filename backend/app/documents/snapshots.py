"""Builds the frozen contents of each document. Pure functions: plain data in, plain data out.

A snapshot holds every value printed on the document, already formatted, so a document always
looks exactly as it did when issued, even if prices, names or policies change later.
Amounts are calculated here by code; the AI is never involved.
"""
from datetime import datetime
from decimal import Decimal

from app.rules.formatting import money

TITLES = {
    "booking_confirmation": "Booking confirmation",
    "payment_receipt": "Payment receipt",
    "fee_receipt": "Fee receipt",
    "release_notice": "Hold released",
}
NUMBER_SUFFIX = {"booking_confirmation": "C", "payment_receipt": "R", "fee_receipt": "F", "release_notice": "N"}
ZERO = Decimal("0.00")


def document_type_for(event: str, action: str, final_amount: Decimal | None) -> str:
    """Which document a settled decision produces."""
    charged = final_amount or ZERO
    if action == "capture" and charged > 0:
        return "payment_receipt" if event == "attended" else "fee_receipt"
    return "release_notice"


def document_number(confirmation_number: str, doc_type: str, sequence: int) -> str:
    """RB-7K2M-9QXD-C1, RB-7K2M-9QXD-R1, ..."""
    return f"{confirmation_number}-{NUMBER_SUFFIX[doc_type]}{sequence}"


def amounts(doc_type: str, price: Decimal, held: Decimal, charged: Decimal) -> dict[str, Decimal]:
    if doc_type == "booking_confirmation":
        return {"charged": ZERO, "held": held, "released": ZERO, "due_after": price - held}
    if doc_type == "payment_receipt":
        return {"charged": charged, "held": ZERO, "released": held - charged, "due_after": max(price - charged, ZERO)}
    if doc_type == "fee_receipt":
        return {"charged": charged, "held": ZERO, "released": held - charged, "due_after": ZERO}
    return {"charged": ZERO, "held": ZERO, "released": held, "due_after": ZERO}  # release_notice


def build_snapshot(
    doc_type: str, *, number: str, issued_at: datetime, issued_local: str,
    business: dict, client: dict, booking: dict, payment: dict, policy: dict,
    charged: Decimal = ZERO, decision: dict | None = None, tax: dict | None = None,
) -> dict:
    currency = booking["currency"]
    sums = amounts(doc_type, Decimal(booking["price"]), Decimal(booking["held"]), Decimal(charged))
    snapshot = {
        "type": doc_type,
        "title": TITLES[doc_type],
        "number": number,
        "issued_at": issued_at.isoformat(),
        "issued_local": issued_local,
        "business": business,              # name, address, phone, timezone
        "client": client,                  # name, phone_masked, attendee
        "booking": {
            "confirmation_number": booking["confirmation_number"],
            "service": booking["service"],
            "staff": booking.get("staff"),
            "duration_minutes": booking["duration_minutes"],
            "when": booking["when"],
            "payment_option": booking["payment_option"],
        },
        "money": {
            "currency": currency,
            "price": money(booking["price"], currency),
            **{key: money(value, currency) for key, value in sums.items()},
        },
        "payment": payment,                # method, card_brand, card_last_digits, paypal_order_id
        "policy": policy,                  # version, lines, free_until
    }
    if decision:
        snapshot["decision"] = decision    # reason, rule (from the rules engine)
    if doc_type == "booking_confirmation":
        snapshot["check_in_token"] = booking["check_in_token"]  # shown as the QR code
    if tax:
        snapshot["tax"] = tax              # tax line, registration number, legal name (frozen)
    return snapshot