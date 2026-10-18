"""A PayPal order and hold for a booking, and everything that happened to it."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey, one_of

PAYMENT_KINDS = ("hold", "remainder", "extra")  # hold at booking; rest of price after; tips or add-ons
PAYMENT_STATUSES = ("created", "authorized", "partially_captured", "captured", "voided", "expired", "failed")
PAYMENT_METHODS = ("paypal", "card")


class Payment(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(one_of("kind", PAYMENT_KINDS), name="kind_valid"),
        CheckConstraint(one_of("status", PAYMENT_STATUSES), name="status_valid"),
        CheckConstraint("method IS NULL OR " + one_of("method", PAYMENT_METHODS), name="method_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("amount_captured >= 0 AND amount_captured <= amount", name="captured_within_amount"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_code"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="hold", server_default="hold")
    status: Mapped[str] = mapped_column(String(20), default="created", server_default="created")

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # authorized (held) amount
    amount_captured: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    currency: Mapped[str] = mapped_column(String(3))

    paypal_order_id: Mapped[str] = mapped_column(String(64), unique=True)
    paypal_authorization_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    payee_merchant_id: Mapped[str | None] = mapped_column(String(64))  # which business account receives it

    # Only what we need to show "Visa •••• 4242". Never the payer's email or name.
    method: Mapped[str | None] = mapped_column(String(10))
    card_brand: Mapped[str | None] = mapped_column(String(30))
    card_last_digits: Mapped[str | None] = mapped_column(String(4))

    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    honor_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # best time to capture
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))            # PayPal's hold expiry
    captures: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    last_paypal_debug_id: Mapped[str | None] = mapped_column(String(64))  # for support if something fails

    booking: Mapped["Booking"] = relationship(back_populates="payments")