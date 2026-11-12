"""What the reviews API accepts and returns."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReviewIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReplyIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=1000)


class ReportIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: str = Field(min_length=5, max_length=300)


class ReviewOut(BaseModel):
    id: uuid.UUID
    rating: int
    comment: str | None
    reviewer: str                 # "Priya S."
    verified_visit: bool = True
    services: str                 # "Haircut + Hair wash"
    visited_month: str            # "Nov 2026"
    created_at: datetime
    edited: bool
    owner_reply: str | None
    owner_replied_at: datetime | None


class MyReviewStatus(BaseModel):
    review: ReviewOut | None
    can_review: bool
    can_edit: bool
    reason: str | None            # why not, in plain words


class RatingSummary(BaseModel):
    average: Decimal | None
    count: int
    distribution: dict[int, int]  # {5: 12, 4: 3, ...}


class ReviewPage(BaseModel):
    summary: RatingSummary
    reviews: list[ReviewOut]
    next_offset: int | None


class OwnerReviewOut(ReviewOut):
    booking_id: uuid.UUID
    reported: bool