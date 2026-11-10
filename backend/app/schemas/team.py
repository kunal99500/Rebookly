"""What the API accepts and returns for staff, their hours, and time off."""
import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.schedule import AvailabilityIn, WeeklyHoursIn

MAX_TIME_OFF = timedelta(days=62)


class StaffCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    service_ids: list[uuid.UUID] | None = Field(default=None, description="Leave empty to offer every service")
    sort_order: int = Field(default=0, ge=0, le=1000)


class StaffUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    service_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def _no_empty_required_fields(self) -> "StaffUpdate":
        for field in ("name", "is_active", "sort_order", "service_ids"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be empty")
        return self


class StaffOut(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    sort_order: int
    service_ids: list[uuid.UUID]
    uses_business_hours: bool          # true when they have no hours of their own
    hours: list[WeeklyHoursIn]


StaffHoursIn = AvailabilityIn          # same shape as business opening hours; empty = use the business's hours


class TimeOffIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    staff_id: uuid.UUID | None = Field(default=None, description="Leave empty to close the whole business")
    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _valid_range(self) -> "TimeOffIn":
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Times must include a time zone, e.g. 2026-10-20T13:00:00+05:30")
        if self.ends_at <= self.starts_at:
            raise ValueError("The end must be after the start")
        if self.ends_at - self.starts_at > MAX_TIME_OFF:
            raise ValueError("Time off can be at most 62 days at a time")
        return self


class TimeOffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    staff_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    reason: str | None


class TimeOffCreated(BaseModel):
    time_off: TimeOffOut
    affected_bookings: int     # confirmed bookings inside this time off, which the owner should move or cancel