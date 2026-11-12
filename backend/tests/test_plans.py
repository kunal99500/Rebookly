from datetime import datetime, timedelta, timezone

from app.rules.plans import plan_from_paypal, pro_active

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def test_pro_is_active_until_the_paid_period_plus_grace():
    assert pro_active("pro", NOW + timedelta(days=10), NOW)
    assert pro_active("pro", NOW - timedelta(days=2), NOW)          # renewal being retried
    assert not pro_active("pro", NOW - timedelta(days=4), NOW)      # lapsed: back to free
    assert not pro_active("free", NOW + timedelta(days=10), NOW)
    assert not pro_active("pro", None, NOW)


def test_paypal_status():
    assert plan_from_paypal("ACTIVE") == "pro"
    assert plan_from_paypal("CANCELLED") == "free" and plan_from_paypal("SUSPENDED") == "free"
