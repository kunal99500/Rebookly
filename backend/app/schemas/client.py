"""What the client API accepts and returns."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProfileIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    # Development only: lets you test with an email sign-in. Ignored unless dev routes are on.
    dev_phone: str | None = Field(default=None, max_length=32)


class ProfileOut(BaseModel):
    name: str
    phone_masked: str | None


class BookingCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    slot_id: uuid.UUID
    payment_option: Literal["deposit_held", "full_held"]
    attendee_name: str | None = Field(default=None, max_length=80)


class BookingStarted(BaseModel):
    booking_id: uuid.UUID
    status: str
    held_amount: Decimal
    currency: str
    payment_expires_at: datetime
    checkout_url: str


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    business_name: str
    service_name: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    price: Decimal
    held_amount: Decimal
    currency: str
    payment_option: str
    confirmation_number: str | None
    attendee_name: str | None