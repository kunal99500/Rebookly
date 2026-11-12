"""What the client API accepts and returns."""
import uuid
import re
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
    email: str | None = None            # verified email, used for confirmations and reminders
    email_pending: str | None = None    # waiting for its code


class EmailIn(BaseModel):
       model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

       email: str | None = Field(default=None, min_length=3, max_length=254)


class EmailCodeIn(BaseModel):
       model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

       code: str = Field(pattern=r"^\d{6}$")

class BookingCreate(BaseModel):
    """A visit: one or more services, at a start time taken from the availability endpoint."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    service_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    starts_at: datetime
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    staff_id: uuid.UUID | None = Field(default=None, description="Leave empty for any available staff member")
    payment_option: Literal["deposit_held", "full_held"]
    attendee_name: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value.lower()

    @field_validator("starts_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("starts_at must include a time zone; use a time from the availability endpoint")
        return value


class ClassBookingCreate(BaseModel):
    """A seat in a group class session (yoga, fitness...), chosen from the class's session list."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    slot_id: uuid.UUID
    name: str = Field(min_length=1, max_length=80)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    payment_option: Literal["deposit_held", "full_held"]
    attendee_name: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value.lower()


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
    check_in_token: str | None = None



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