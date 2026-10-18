"""Clients waiting for a slot to open, and the offers made to them."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey, one_of

WAITLIST_STATUSES = ("waiting", "offered", "booked", "declined", "removed")


class WaitlistEntry(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        CheckConstraint(one_of("status", WAITLIST_STATUSES), name="status_valid"),
        # An entry is "offered" exactly when it has an offered slot and an offer deadline.
        CheckConstraint(
            "(status = 'offered') = (offered_slot_id IS NOT NULL AND offer_expires_at IS NOT NULL)",
            name="offer_fields_match_status",
        ),
        Index("ix_waitlist_entries_lookup", "business_id", "service_id", "status"),
        # A client can only have one active waitlist entry per service.
        Index(
            "uq_waitlist_entries_one_active", "client_id", "service_id", unique=True,
            postgresql_where=text("status IN ('waiting', 'offered')"),
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"))
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))  # e.g. weekday evenings
    status: Mapped[str] = mapped_column(String(20), default="waiting", server_default="waiting")

    # Filled while an offer is open ("held for you for 15 minutes").
    offered_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("slots.id", ondelete="SET NULL")
    )
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The booking created when the client accepted an offer.
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL")
    )