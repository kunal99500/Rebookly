"""Turns a structured policy into short, plain sentences for clients. Deterministic: no AI.

The same sentences appear on the booking page and the confirmation, so clients always
read exactly the rules the engine will apply.
"""
from decimal import Decimal

from app.rules.engine import Fee, FeeKind, Policy


def _fee_text(fee: Fee) -> str:
    if fee.kind == FeeKind.PERCENT_OF_HOLD:
        value = fee.value.normalize()
        if value == 100:
            return "your full hold"
        return f"{value:f}% of your hold"
    return f"up to {fee.value:.2f} of your hold"


def _is_free(fee: Fee) -> bool:
    return fee.value == Decimal("0")


def policy_summary(policy: Policy) -> list[str]:
    lines = []
    if policy.free_cancel_hours > 0:
        hours = policy.free_cancel_hours
        unit = "hour" if hours == 1 else "hours"
        lines.append(f"Free cancellation up to {hours} {unit} before your appointment.")
        if _is_free(policy.late_cancel_fee):
            lines.append("Cancelling later is also free.")
        else:
            lines.append(f"Cancelling later: {_fee_text(policy.late_cancel_fee)} may be kept.")
    elif _is_free(policy.late_cancel_fee):
        lines.append("You can cancel for free at any time before your appointment.")
    else:
        lines.append(f"Cancelling: {_fee_text(policy.late_cancel_fee)} may be kept.")

    if _is_free(policy.no_show_fee):
        lines.append("No charge if you miss your appointment.")
    else:
        lines.append(f"Missing your appointment: {_fee_text(policy.no_show_fee)} may be kept.")

    if policy.waive_if_refilled and not (_is_free(policy.late_cancel_fee) and _is_free(policy.no_show_fee)):
        lines.append("No fee if someone else takes your slot.")
    if policy.grace_minutes > 0:
        lines.append(f"Running up to {policy.grace_minutes} minutes late is fine.")
    return lines