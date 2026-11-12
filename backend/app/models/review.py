"""Verified reviews: one per attended booking. Owners can reply and report, but never hide or edit."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class Review(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        CheckConstraint("char_length(comment) <= 1000", name="comment_length"),
        CheckConstraint("char_length(owner_reply) <= 1000", name="reply_length"),
        Index("ix_reviews_business_newest", "business_id", "created_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"),
                                                  unique=True)               # one review per visit
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # from the booking, for "visited in March"
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_reply: Mapped[str | None] = mapped_column(Text)
    owner_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))   # for Rebookly to look at
    report_reason: Mapped[str | None] = mapped_column(String(300))