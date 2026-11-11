"""What the client API accepts and returns."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    # Development only: lets you test with an email sign-in. Ignored unless dev routes are on.
    dev_phone: str | None = Field(default=None, max_length=32)


class ProfileOut(BaseModel):
    name: str
    phone_masked: str | None


class BookingCreate(BaseModel):
    """A visit: one or more services, at a start time taken from the availability endpoint."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    service_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    starts_at: datetime
    staff_id: uuid.UUID | None = Field(default=None, description="Leave empty for any available staff member")
    payment_option: Literal["deposit_held", "full_held"]
    attendee_name: str | None = Field(default=None, max_length=80)

    @field_validator("starts_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("starts_at must include a time zone; use a time from the availability endpoint")
        return value


class BookingStarted(BaseModel):
    booking_id: uuid.UUID
    status: str
    held_amount: Decimal
    currency: str
    payment_expires_at: datetime
    checkout_url: str


class BookingItemOut(BaseModel):
    name: str
    kind: str
    duration_minutes: int
    price: Decimal


class BookingOut(BaseModel):
    id: uuid.UUID
    status: str
    business_name: str
    service_name: str               # e.g. "Haircut + Hair wash"
    items: list[BookingItemOut]
    staff_name: str | None
    starts_at: datetime
    ends_at: datetime
    timezone: str
    price: Decimal
    held_amount: Decimal
    currency: str
    payment_option: str
    confirmation_number: str | None
    attendee_name: str | None



class RescheduleIn(BaseModel):
    """Move a booking to a time taken from the reschedule-options endpoint."""
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime
    staff_id: uuid.UUID | None = Field(default=None, description="Leave empty to keep your staff member if free")

    @field_validator("starts_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("starts_at must include a time zone; use a time from reschedule-options")
        return value


class RescheduleOption(BaseModel):
    starts_at: datetime
    ends_at: datetime