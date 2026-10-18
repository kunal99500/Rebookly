"""A business using Rebookly: salon, trainer, tutor, and so on."""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey, one_of

BUSINESS_STATUSES = ("draft", "live", "paused")
PAYPAL_STATUSES = ("not_connected", "connected", "needs_attention")


class Business(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint(one_of("status", BUSINESS_STATUSES), name="status_valid"),
        CheckConstraint(one_of("paypal_status", PAYPAL_STATUSES), name="paypal_status_valid"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_code"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"),
    )

    # The owner's Supabase login ID. Only this user can manage the business.
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True)      # booking link: /b/lumen-fitness
    category: Mapped[str] = mapped_column(String(40))               # matches a category template
    vocabulary: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    privacy_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")

    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    listed_publicly: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    paypal_status: Mapped[str] = mapped_column(String(20), default="not_connected", server_default="not_connected")
    paypal_merchant_id: Mapped[str | None] = mapped_column(String(64))

    # Which saved policy version applies to new bookings.
    current_policy_version: Mapped[int | None] = mapped_column(Integer)

    services: Mapped[list["Service"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", order_by="Service.sort_order"
    )
    policies: Mapped[list["BusinessPolicy"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", order_by="BusinessPolicy.version"
    )