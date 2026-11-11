"""Tests for keeping payments in line with PayPal (no network)."""
import pytest

from app.rules.paypal_sync import category, references, sync


@pytest.mark.parametrize("ours, paypal, kind, new", [
    ("authorized", "CREATED", "none", None),                  # nothing changed
    ("authorized", "VOIDED", "update", "voided"),             # voided on PayPal's side
    ("authorized", "EXPIRED", "update", "expired"),           # the hold ran out
    ("authorized", "CAPTURED", "update", "captured"),         # captured (e.g. our reply was lost)
    ("created", "CREATED", "update", "authorized"),           # authorized, but our page never finished
    ("partially_captured", "CREATED", "conflict", "authorized"),  # can't go backwards
    ("voided", "CAPTURED", "conflict", "captured"),           # we think voided, PayPal says captured
    ("captured", "CAPTURED", "none", None),
    ("authorized", "SOMETHING_NEW", "none", None),            # unknown status: leave it
])
def test_sync_decisions(ours, paypal, kind, new):
    result = sync(ours, paypal)
    assert (result.kind, result.new_status) == (kind, new)


def test_event_categories():
    assert category("PAYMENT.AUTHORIZATION.VOIDED") == "authorization"
    assert category("CHECKOUT.ORDER.APPROVED") == "order_approved"
    assert category("BILLING.SUBSCRIPTION.CREATED") == "ignore"


def test_references_keep_only_ids():
    capture = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {
        "id": "CAP-1", "payer": {"email_address": "client@example.com"},
        "supplementary_data": {"related_ids": {"authorization_id": "AUTH-1", "order_id": "ORDER-1"}}}}
    assert references(capture) == {"capture_id": "CAP-1", "authorization_id": "AUTH-1", "order_id": "ORDER-1"}
    dispute = {"event_type": "CUSTOMER.DISPUTE.CREATED", "resource": {
        "dispute_id": "PP-D-1", "disputed_transactions": [{"seller_transaction_id": "CAP-1"}]}}
    assert references(dispute) == {"dispute_id": "PP-D-1", "capture_ids": ["CAP-1"]}
    assert references({"event_type": "PAYMENT.AUTHORIZATION.VOIDED", "resource": {"id": "AUTH-9"}}) == {"authorization_id": "AUTH-9"}