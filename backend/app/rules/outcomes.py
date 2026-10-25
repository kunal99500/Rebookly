"""Pure rules around booking outcomes (check-in window, decision and payment states). No database, no PayPal."""
from datetime import datetime, timedelta
from decimal import Decimal

from app.rules.engine import Action, Decision

CHECK_IN_OPENS_BEFORE = timedelta(minutes=60)       # QR check-in opens an hour before the start
CHECK_IN_CLOSES_AFTER_END = timedelta(hours=2)      # and stays open until two hours after the end


def can_check_in(starts_at: datetime, ends_at: datetime, now: datetime) -> bool:
    return starts_at - CHECK_IN_OPENS_BEFORE <= now <= ends_at + CHECK_IN_CLOSES_AFTER_END


def initial_status(decision: Decision) -> str:
    """Fees and exceptions wait for the owner; anything the policy allows outright runs straight away."""
    if decision.action == Action.OWNER_DECIDES or decision.needs_owner_approval:
        return "pending_approval"
    return "approved"


def payment_status_after_capture(held: Decimal, captured: Decimal) -> str:
    """A capture with final_capture=True releases whatever wasn't captured."""
    return "captured" if captured >= held else "partially_captured"


def masked_last4(last4: str | None) -> str | None:
    return f"•••• {last4}" if last4 else None