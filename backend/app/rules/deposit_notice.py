"""The deposit notice clients see before they pay. Written by code from the real amounts and policy,
so it can never hide or misstate what's held. The owner only chooses WHEN it appears and may add a note."""
from decimal import Decimal

from app.rules.engine import Fee
from app.rules.formatting import money

TIMINGS = ("business_page", "booking_start", "checkout")   # never after payment


def build_notice(
    *, hold: Decimal, total: Decimal, currency: str, payment_option: str,
    free_cancel_hours: int, late_cancel_fee: Fee, no_show_fee: Fee, owner_note: str | None = None,
) -> dict:
    hold = Decimal(hold)
    pay_later = max(Decimal(total) - hold, Decimal("0.00"))
    late = min(late_cancel_fee.amount_for(hold), hold)
    no_show = min(no_show_fee.amount_for(hold), hold)
    lines = [
        {"label": "Held now (not charged)", "amount": money(hold, currency)},
        {"label": "Pay at the business" if pay_later > 0 else "Nothing more to pay later",
         "amount": money(pay_later, currency)},
    ]
    policy = []
    if free_cancel_hours > 0:
        policy.append(f"Free cancellation up to {free_cancel_hours} hours before.")
        policy.append(f"Late cancellation keeps {money(late, currency)}." if late > 0
                      else "Late cancellations are free too.")
    else:
        policy.append(f"Cancelling keeps {money(late, currency)}." if late > 0 else "Cancelling is free.")
    policy.append(f"Not showing up keeps {money(no_show, currency)}." if no_show > 0 else "No fee for not showing up.")
    return {
        "title": "Before you book",
        "summary": f"{money(hold, currency)} will be held on your card or PayPal. It isn't charged now.",
        "lines": lines,
        "policy": policy,
        "owner_note": owner_note or None,
        "payment_option": payment_option,
    }