"""The deposit rule an owner chooses once ("10% of the price"), applied to every service. Pure rules.

Amounts are rounded to whole units of the currency (₹30, not ₹29.70), never above the price,
and never below a small minimum that still means something.
"""
from decimal import ROUND_HALF_UP, Decimal

SUGGESTED_PERCENT = Decimal("10")
PERCENT_CHOICES = (Decimal("10"), Decimal("20"), Decimal("30"), Decimal("50"))
# The smallest deposit worth holding, per currency (also kept above PayPal's own minimums).
MINIMUM = {"INR": Decimal("20"), "USD": Decimal("2"), "GBP": Decimal("2"), "EUR": Decimal("2"),
           "AUD": Decimal("3"), "CAD": Decimal("3"), "AED": Decimal("10"), "SGD": Decimal("3")}
DEFAULT_MINIMUM = Decimal("2")


def minimum_for(currency: str) -> Decimal:
    return MINIMUM.get(currency.upper(), DEFAULT_MINIMUM)


def deposit_for(*, price: Decimal, currency: str, percent: Decimal | None = None,
                fixed: Decimal | None = None) -> Decimal:
    """The deposit for one service: a fixed amount, or a percent of the price, rounded to whole units."""
    if price <= 0:
        return Decimal("0.00")
    if fixed is not None:
        amount = fixed
    else:
        amount = (price * (percent if percent is not None else SUGGESTED_PERCENT) / 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP)
    amount = max(amount, minimum_for(currency))
    return min(amount, price).quantize(Decimal("0.01"))
