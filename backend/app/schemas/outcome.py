"""What the API accepts and returns for booking outcomes and the decisions they create."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    event: str
    action: str
    amount: Decimal                 # what the policy allows
    final_amount: Decimal | None    # what was actually charged (owner may lower it)
    rule: str
    reason: str
    fee_capped: bool
    needs_owner_approval: bool
    status: str
    owner_note: str | None
    failure_reason: str | None
    created_at: datetime
    executed_at: datetime | None


class OutcomeOut(BaseModel):
    booking_status: str
    decision: DecisionOut | None
    message: str


class CheckInIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=100)  # read from the client's QR code


class ApproveIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    final_amount: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2,
                                         description="Optional: charge less than the policy allows")
    note: str | None = Field(default=None, max_length=500)


class WaiveIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class CancelPreviewOut(BaseModel):
    """What would happen if the client cancelled right now. Nothing is changed."""
    fee: Decimal
    released: Decimal
    currency: str
    needs_owner_approval: bool
    reason: str


class OwnerBookingOut(BaseModel):
    id: uuid.UUID
    status: str
    service_name: str
    starts_at: datetime
    ends_at: datetime
    client_name: str
    client_phone: str | None       # masked, e.g. •••• 3456
    attendee_name: str | None
    held_amount: Decimal
    currency: str
    payment_option: str
    payment_status: str | None
    confirmation_number: str | None
    checked_in_at: datetime | None