"""Something a business sells: a haircut, a training session, a tutoring hour."""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey

PAYMENT_OPTIONS = ("deposit_held", "full_held")  # MVP options; "pay_now" and "no_hold" come later


class Service(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_minutes BETWEEN 5 AND 720", name="duration_range"),
        CheckConstraint("price >= 0", name="price_not_negative"),
        CheckConstraint("deposit >= 0 AND deposit <= price", name="deposit_within_price"),
        CheckConstraint("capacity BETWEEN 1 AND 500", name="capacity_range"),
        CheckConstraint(
            "jsonb_typeof(payment_options) = 'array' AND jsonb_array_length(payment_options) > 0",
            name="has_payment_option",
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    capacity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # >1 for group classes later
    payment_options: Mapped[list] = mapped_column(
        JSONB, default=lambda: ["deposit_held"], server_default=text("""'["deposit_held"]'::jsonb""")
    )
    # Optional stricter policy for this service only (e.g. a $300 photo shoot). Same format as the engine's Policy.
    policy_override: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    business: Mapped["Business"] = relationship(back_populates="services")