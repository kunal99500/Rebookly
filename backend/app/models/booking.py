"""One booking: who, with whom, when, what's held, which policy applies, and what happened.

   Double-booking of a staff member is refused by the database itself: the migration adds an
   exclusion constraint so no two active appointments for the same staff member can overlap.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey, one_of

BOOKING_STATUSES = ("pending_payment", "confirmed", "cancelled", "attended", "no_show", "expired")
PAYMENT_OPTIONS = ("deposit_held", "full_held")
CANCELLED_BY = ("client", "owner")


class Booking(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(one_of("status", BOOKING_STATUSES), name="status_valid"),
        CheckConstraint(one_of("payment_option", PAYMENT_OPTIONS), name="payment_option_valid"),
        CheckConstraint("cancelled_by IS NULL OR " + one_of("cancelled_by", CANCELLED_BY), name="cancelled_by_valid"),
        CheckConstraint("price >= 0", name="price_not_negative"),
        CheckConstraint("held_amount >= 0 AND held_amount <= price", name="held_within_price"),
        CheckConstraint("ends_at > starts_at", name="ends_after_start"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_code"),
        Index("ix_bookings_business_start", "business_id", "starts_at"),
        Index("ix_bookings_client", "client_id"),
        Index("ix_bookings_slot", "slot_id"),
        Index("ix_bookings_staff_start", "staff_id", "starts_at"),
        CheckConstraint("occupied_until >= ends_at", name="occupied_after_end"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"))
    slot_id: Mapped[uuid.UUID | None] = mapped_column(  # only for class bookings
           UUID(as_uuid=True), ForeignKey("slots.id", ondelete="RESTRICT")
       )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
           UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT")
       )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
           UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT")
       )
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"))
    attendee_name: Mapped[str | None] = mapped_column(String(80))  # when booking for someone else

    status: Mapped[str] = mapped_column(String(20), default="pending_payment", server_default="pending_payment")
    payment_option: Mapped[str] = mapped_column(String(20))

    # Copied at booking time, so later price or policy changes never affect this booking.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    held_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    policy_version: Mapped[int] = mapped_column(Integer)
    policy_snapshot: Mapped[dict] = mapped_column(JSONB)  # exactly what the rules engine will use
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occupied_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # ends_at + cleanup time
    payment_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # seat released after this
    confirmation_number: Mapped[str | None] = mapped_column(String(40), unique=True)       # e.g. RB-LUMEN-00042
    check_in_token: Mapped[str] = mapped_column(String(64), unique=True)                   # secret inside the QR code

    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[str | None] = mapped_column(String(10))
    no_show_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL")
    )

    payments: Mapped[list["Payment"]] = relationship(back_populates="booking", order_by="Payment.created_at")