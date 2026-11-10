"""What the public "available times" endpoint accepts and returns."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_ids: list[uuid.UUID] = Field(min_length=1, max_length=10, description="Main service(s) first, then add-ons")
    staff_id: uuid.UUID | None = Field(default=None, description="Leave empty for any available staff member")


class StaffChoice(BaseModel):
    id: uuid.UUID
    name: str


class TimeChoice(BaseModel):
    starts_at: datetime
    ends_at: datetime
    staff: list[StaffChoice]   # who is free at this time (first = suggested)


class AvailabilityOut(BaseModel):
    duration_minutes: int
    price: Decimal
    deposit: Decimal
    currency: str
    payment_options: list[str]
    staff_choices: list[StaffChoice]   # everyone who can do this combination
    times: list[TimeChoice]