"""What the API accepts and returns for opening hours and slots."""
import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.rules.scheduling import WeeklyHours, check_no_overlaps


class WeeklyHoursIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday")
    start: time
    end: time

    @field_validator("start", "end")
    @classmethod
    def _whole_minutes(cls, value: time) -> time:
        if value.second or value.microsecond or value.tzinfo:
            raise ValueError("Use local times in hours and minutes, like 09:30")
        return value

    @model_validator(mode="after")
    def _end_after_start(self) -> "WeeklyHoursIn":
        if self.end <= self.start:
            raise ValueError("Closing time must be after opening time")
        return self


class AvailabilityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hours: list[WeeklyHoursIn] = Field(max_length=50)

    @model_validator(mode="after")
    def _no_overlaps(self) -> "AvailabilityIn":
        check_no_overlaps([WeeklyHours(h.weekday, h.start, h.end) for h in self.hours])
        return self


class AvailabilityOut(BaseModel):
    timezone: str
    hours: list[WeeklyHoursIn]


class GenerateSlotsOut(BaseModel):
    created: int
    services: int
    days: int


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    capacity: int
    booked_count: int
    is_blocked: bool
    bookable: bool = False  # inside the booking window, not blocked, not full


class SlotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_blocked: bool