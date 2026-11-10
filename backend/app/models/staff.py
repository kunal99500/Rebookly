"""People who perform services, which services each one does, and their own working hours."""
import uuid
from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, SmallInteger, String, Time, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class Staff(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "staff"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # set when the person has a login
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class StaffService(Base):
    """Which services each staff member can perform."""
    __tablename__ = "staff_services"

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class StaffHours(UUIDPrimaryKey, Timestamps, Base):
    """A staff member's own weekly hours. If they have none, the business's opening hours are used."""
    __tablename__ = "staff_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("end_time > start_time", name="ends_after_start"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)   # local time
    end_time: Mapped[time] = mapped_column(Time)