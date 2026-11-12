"""Which plan a business is on right now. Pure rules, no database.

  * free: no monthly price; Rebookly keeps 3% of money a client pays for a visit.
  * pro:  a monthly PayPal subscription; no per-visit fee while it's paid up.
A lapsed or cancelled subscription simply falls back to the free plan, after a short grace period.
"""
from datetime import datetime, timedelta

GRACE = timedelta(days=3)   # PayPal retries a failed renewal for a few days


def pro_active(plan: str, pro_until: datetime | None, now: datetime) -> bool:
    return plan == "pro" and pro_until is not None and now <= pro_until + GRACE


def plan_from_paypal(status: str) -> str:
    """PayPal subscription status -> our plan."""
    return "pro" if status.upper() in {"ACTIVE", "APPROVED"} else "free"
