"""What the owner's "needs attention" panel returns."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AttentionBooking(BaseModel):
    booking_id: uuid.UUID
    client_name: str
    service_name: str
    starts_at: datetime
    held_amount: Decimal
    currency: str


class AttentionOut(BaseModel):
    possible_no_shows: list[AttentionBooking]   # grace period over, nobody checked in
    pending_approvals: int                      # fees waiting for the owner
    failed_payments: int                        # PayPal actions to retry
    holds_ending_soon: list[AttentionBooking]   # hold's best-capture window ends within 12 hours