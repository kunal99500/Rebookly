"""Permanent audit log: every money action and every sensitive data access. Never edited or deleted."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import one_of

ACTOR_TYPES = ("system", "owner", "client", "paypal", "ai")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(one_of("actor_type", ACTOR_TYPES), name="actor_type_valid"),
        Index("ix_audit_events_business_time", "business_id", "occurred_at"),
        Index("ix_audit_events_booking", "booking_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)

    # Plain IDs, deliberately without foreign keys, so the log survives even if records are deleted.
    business_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    actor_type: Mapped[str] = mapped_column(String(10))       # who did it
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(60))           # e.g. "payment.captured", "client.phone_viewed"
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))  # never secrets
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())