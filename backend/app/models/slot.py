"""A bookable time for one service, e.g. 1:1 training on Tue 20 Oct at 7:00."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class Slot(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "slots"
    __table_args__ = (
        UniqueConstraint("service_id", "starts_at", name="uq_slots_service_start"),
        CheckConstraint("ends_at > starts_at", name="ends_after_start"),
        CheckConstraint("capacity BETWEEN 1 AND 500", name="capacity_range"),
        CheckConstraint("booked_count >= 0 AND booked_count <= capacity", name="booked_within_capacity"),
        Index("ix_slots_business_start", "business_id", "starts_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")       # 1 for appointments
    booked_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")   # seats taken or being paid for
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))  # owner closed it