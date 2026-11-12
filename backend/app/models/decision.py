"""Every rules engine decision about a booking's money, and what the owner did with it."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey, one_of

# These match the rules engine's Event and Action values exactly.
DECISION_EVENTS = ("attended", "client_cancelled", "rescheduled", "no_show", "owner_cancelled", "exception_claimed")
DECISION_ACTIONS = ("capture", "void", "keep_hold", "wait", "owner_decides")
DECISION_STATUSES = ("pending_approval", "approved", "waived", "executing", "executed", "failed", "superseded")


class Decision(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(one_of("event", DECISION_EVENTS), name="event_valid"),
        CheckConstraint(one_of("action", DECISION_ACTIONS), name="action_valid"),
        CheckConstraint(
            "suggested_action IS NULL OR " + one_of("suggested_action", DECISION_ACTIONS), name="suggested_action_valid"
        ),
        CheckConstraint(one_of("status", DECISION_STATUSES), name="status_valid"),
        CheckConstraint("amount >= 0", name="amount_not_negative"),
        # The owner may lower a fee, never raise it above what the engine allowed.
        CheckConstraint("final_amount IS NULL OR (final_amount >= 0 AND final_amount <= amount)",
                        name="final_amount_within_recommended"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), index=True
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT")
    )

    # Exactly what the rules engine returned.
    event: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rule: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(Text)
    fee_capped: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    needs_owner_approval: Mapped[bool] = mapped_column(Boolean)
    suggested_action: Mapped[str | None] = mapped_column(String(20))

    # What happened next.
    status: Mapped[str] = mapped_column(String(20))
    final_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # what was actually charged
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_note: Mapped[str | None] = mapped_column(String(500))

    # Sent to PayPal as the PayPal-Request-Id, so retrying this decision can never charge twice.
    paypal_request_id: Mapped[str] = mapped_column(String(100), unique=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(500))
    last_paypal_debug_id: Mapped[str | None] = mapped_column(String(64))
    platform_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))   # Rebookly's 3%, if any