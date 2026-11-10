"""Breaks and days off, for one staff member or (staff_id empty) the whole business."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class TimeOff(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "time_off"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_start"),
        Index("ix_time_off_business_start", "business_id", "starts_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(120))   # e.g. "Lunch", "Holiday" (shown to the owner only)