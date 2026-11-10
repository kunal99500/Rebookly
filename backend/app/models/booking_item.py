"""Each service in a booking, with its name, price and duration frozen at booking time."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKey, one_of


class BookingItem(UUIDPrimaryKey, Base):
    __tablename__ = "booking_items"
    __table_args__ = (
        UniqueConstraint("booking_id", "position", name="uq_booking_items_booking_position"),
        CheckConstraint(one_of("kind", ("main", "add_on")), name="kind_valid"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("price >= 0 AND deposit >= 0", name="amounts_not_negative"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(SmallInteger)      # order within the visit: 1, 2, 3
    kind: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(120))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())