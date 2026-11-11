"""Keeping our payment records in line with PayPal. Pure functions, no database or network.

Webhooks only tell us *that* something changed. We always ask PayPal for the current state and
compare it with ours: PayPal is the source of truth for money, our records follow it.
"""
from dataclasses import dataclass

# PayPal authorization status -> our payment status
AUTHORIZATION_STATUS = {
    "CREATED": "authorized", "PENDING": "authorized",
    "PARTIALLY_CAPTURED": "partially_captured", "CAPTURED": "captured",
    "VOIDED": "voided", "EXPIRED": "expired", "DENIED": "failed",
}
OPEN = ("created", "authorized", "partially_captured")
ORDER = {"created": 0, "authorized": 1, "partially_captured": 2}

EVENT_CATEGORIES = {
    "CHECKOUT.ORDER.APPROVED": "order_approved",
    "PAYMENT.AUTHORIZATION.CREATED": "authorization",
    "PAYMENT.AUTHORIZATION.VOIDED": "authorization",
    "PAYMENT.CAPTURE.COMPLETED": "capture",
    "PAYMENT.CAPTURE.DENIED": "capture",
    "PAYMENT.CAPTURE.PENDING": "capture",
    "PAYMENT.CAPTURE.REFUNDED": "capture",
    "PAYMENT.CAPTURE.REVERSED": "capture",
    "CUSTOMER.DISPUTE.CREATED": "dispute",
}


@dataclass(frozen=True)
class SyncResult:
    kind: str                    # "none", "update" or "conflict"
    new_status: str | None = None


def category(event_type: str) -> str:
    return EVENT_CATEGORIES.get(event_type, "ignore")


def sync(ours: str, paypal_status: str) -> SyncResult:
    """What to do when PayPal's authorization status is known."""
    theirs = AUTHORIZATION_STATUS.get((paypal_status or "").upper())
    if theirs is None or theirs == ours:
        return SyncResult("none")
    if ours in OPEN:
        if theirs in ORDER and ORDER[theirs] < ORDER[ours]:
            return SyncResult("conflict", theirs)     # PayPal can't go backwards; flag it
        return SyncResult("update", theirs)           # forward progress (e.g. voided or expired on PayPal's side)
    return SyncResult("conflict", theirs)             # ours is final but PayPal disagrees: needs a person


def references(event: dict) -> dict:
    """The IDs we need from an event. Nothing else is kept (events contain payer names and emails)."""
    resource = event.get("resource") or {}
    kind = category(event.get("event_type", ""))
    refs: dict = {}
    if kind == "order_approved":
        refs["order_id"] = resource.get("id")
    elif kind == "authorization":
        refs["authorization_id"] = resource.get("id")
    elif kind == "capture":
        related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
        refs.update(capture_id=resource.get("id"), authorization_id=related.get("authorization_id"),
                    order_id=related.get("order_id"))
    elif kind == "dispute":
        refs["dispute_id"] = resource.get("dispute_id")
        refs["capture_ids"] = [t.get("seller_transaction_id") for t in resource.get("disputed_transactions") or []
                               if t.get("seller_transaction_id")]
    return {k: v for k, v in refs.items() if v}