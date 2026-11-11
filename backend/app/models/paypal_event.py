"""PayPal webhook events we've received: one row per event, so each is handled exactly once.

Only IDs are kept (in refs), never the full event: PayPal events contain payer names and emails.
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKey, one_of

STATUSES = ("received", "processed", "ignored", "failed")


class PayPalWebhookEvent(UUIDPrimaryKey, Base):
    __tablename__ = "paypal_webhook_events"
    __table_args__ = (CheckConstraint(one_of("status", STATUSES), name="status_valid"),)

    paypal_event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(80))
    refs: Mapped[dict] = mapped_column(JSONB, default=dict)         # authorization / order / capture / dispute IDs
    status: Mapped[str] = mapped_column(String(10), default="received", server_default="received")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(300))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))