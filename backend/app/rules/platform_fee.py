"""Rebookly's own fee. Pure rules, no database.

Plans:
  * free: Rebookly keeps 3% of money a client actually pays for a visit.
  * pro:  a monthly subscription, and no per-visit fee.

The fee is split off inside the same PayPal payment, at the moment money moves (when the hold is
charged at the visit). Nothing to do with a cancellation ever pays Rebookly: a released deposit, a late
cancellation fee and a no-show fee all have no platform fee.
"""
from decimal import ROUND_HALF_UP, Decimal

FREE_PLAN_RATE = Decimal("0.03")
PLANS = ("free", "pro")
FEE_FREE_EVENTS = frozenset({"client_cancelled", "owner_cancelled", "no_show"})
CENT = Decimal("0.01")


def platform_fee(*, amount: Decimal, event: str, action: str, plan: str, pro_active: bool,
                 rate: Decimal = FREE_PLAN_RATE) -> Decimal:
    """The fee for one money movement. Zero unless a client is paying for a visit on the free plan."""
    if action != "capture" or event in FEE_FREE_EVENTS or amount <= 0:
        return Decimal("0.00")
    if plan == "pro" and pro_active:
        return Decimal("0.00")
    return (amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)


def owner_receives(amount: Decimal, fee: Decimal) -> Decimal:
    return (amount - fee).quantize(CENT)
