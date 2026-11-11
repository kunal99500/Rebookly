"""What the waitlist API accepts and returns."""
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WaitlistJoin(BaseModel):
    """Join the waitlist for an appointment (services + day + time window) or for a full class session."""
    model_config = ConfigDict(extra="forbid")

    service_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    wanted_date: date | None = None
    earliest_time: time | None = Field(default=None, description="Local time, e.g. 16:00")
    latest_time: time | None = Field(default=None, description="Local time, e.g. 19:00")
    slot_id: uuid.UUID | None = Field(default=None, description="For a full class session instead")

    @model_validator(mode="after")
    def _one_kind(self) -> "WaitlistJoin":
        if self.slot_id is not None:
            if self.service_ids or self.wanted_date or self.earliest_time or self.latest_time:
                raise ValueError("For a class, send only slot_id")
            return self
        if not (self.service_ids and self.wanted_date and self.earliest_time and self.latest_time):
            raise ValueError("Send service_ids, wanted_date, earliest_time and latest_time")
        if self.earliest_time >= self.latest_time:
            raise ValueError("earliest_time must be before latest_time")
        return self


class WaitlistOut(BaseModel):
    id: uuid.UUID
    business_name: str
    business_slug: str
    visit: str
    wanted_date: date
    earliest_time: time
    latest_time: time
    status: str
    offered_starts_at: datetime | None
    offer_expires_at: datetime | None