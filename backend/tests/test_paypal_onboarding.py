"""Tests for checking a business's connected PayPal account (no network)."""
import uuid

from app.rules.paypal_onboarding import check_integration, tracking_id

READY = {"merchant_id": "MERCHANT1", "payments_receivable": True, "primary_email_confirmed": True,
         "oauth_integrations": [{"integration_type": "OAUTH_THIRD_PARTY"}]}


def test_ready_account_is_connected():
    check = check_integration(READY)
    assert check.status == "connected" and check.problems == ()


def test_each_problem_is_explained():
    check = check_integration({**READY, "payments_receivable": False, "primary_email_confirmed": False,
                               "oauth_integrations": []})
    assert check.status == "needs_attention" and len(check.problems) == 3
    assert any("receive payments" in p for p in check.problems)
    assert any("Confirm your email" in p for p in check.problems)


def test_missing_details_are_not_treated_as_ready():
    assert check_integration({}).status == "needs_attention"


def test_tracking_id_identifies_the_business():
    business_id = uuid.uuid4()
    assert tracking_id(business_id) == f"rebookly-{business_id}" and len(tracking_id(business_id)) <= 127