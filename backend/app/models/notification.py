"""The notification outbox: one row per message, saved in the same transaction as the change it's about.

A background job sends pending rows and retries failures. dedupe_key makes every message unique,
so the same event can never produce the same message twice.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKey, one_of

CHANNELS = ("email", "sms")
RECIPIENTS = ("owner", "client")
STATUSES = ("pending", "sent", "failed")


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(one_of("channel", CHANNELS), name="channel_valid"),
        CheckConstraint(one_of("recipient_type", RECIPIENTS), name="recipient_type_valid"),
        CheckConstraint(one_of("status", STATUSES), name="status_valid"),
        Index("ix_notifications_due", "status", "next_attempt_at"),
    )

    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(10))
    recipient_type: Mapped[str] = mapped_column(String(10))
    to_address: Mapped[str] = mapped_column(String(320))
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSONB)             # the frozen facts the message is written from
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
    provider_message_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))