"""The waitlist: clients who'd like a time that's currently taken.

When a booking is cancelled, matching clients are offered the freed time (the first to book gets it).
Appointments wait for a date and a time window; classes wait for a seat in one session.
"""
import uuid
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Time, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey, one_of

WAITLIST_STATUSES = ("waiting", "offered", "booked", "expired", "removed")


class WaitlistEntry(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "waitlist_requests"
    __table_args__ = (
        CheckConstraint(one_of("status", WAITLIST_STATUSES), name="status_valid"),
        CheckConstraint("earliest_time < latest_time", name="window_valid"),
        CheckConstraint("(status = 'offered') = (offered_starts_at IS NOT NULL AND offer_expires_at IS NOT NULL)",
                        name="offer_fields_match_status"),
        Index("ix_waitlist_requests_lookup", "business_id", "wanted_date", "status"),
        Index("uq_waitlist_requests_one_per_day", "client_id", "business_id", "wanted_date", unique=True,
              postgresql_where=text("status IN ('waiting', 'offered')")),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    service_ids: Mapped[list] = mapped_column(JSONB)                 # the visit wanted, e.g. haircut + wash
    slot_id: Mapped[uuid.UUID | None] = mapped_column(                # set for a class session
        UUID(as_uuid=True), ForeignKey("slots.id", ondelete="CASCADE"))
    wanted_date: Mapped[date] = mapped_column(Date)                   # in the business's time zone
    earliest_time: Mapped[time] = mapped_column(Time)                 # local times: the visit should start
    latest_time: Mapped[time] = mapped_column(Time)                   # between these two
    status: Mapped[str] = mapped_column(String(10), default="waiting", server_default="waiting")
    offered_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL"))