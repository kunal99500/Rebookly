"""A business's regular weekly opening hours, e.g. Monday 07:00-12:00 (in the business's own time zone)."""
import uuid
from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class AvailabilityRule(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "availability_rules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),  # 0 = Monday ... 6 = Sunday
        CheckConstraint("end_time > start_time", name="ends_after_start"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)  # local time, no date
    end_time: Mapped[time] = mapped_column(Time)