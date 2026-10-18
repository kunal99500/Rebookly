"""Receipts and confirmations. Frozen when issued: changes create a new document."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKey, one_of

DOCUMENT_TYPES = (
    "booking_confirmation", "updated_confirmation", "payment_receipt",
    "release_notice", "fee_receipt", "refund_receipt",
)


class Document(UUIDPrimaryKey, Base):
    __tablename__ = "documents"
    __table_args__ = (CheckConstraint(one_of("type", DOCUMENT_TYPES), name="type_valid"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), index=True
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.id", ondelete="RESTRICT")
    )
    replaces_document_id: Mapped[uuid.UUID | None] = mapped_column(  # e.g. an updated confirmation
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT")
    )

    type: Mapped[str] = mapped_column(String(30))
    number: Mapped[str] = mapped_column(String(50), unique=True)       # printed reference
    snapshot: Mapped[dict] = mapped_column(JSONB)                      # every value shown, frozen at issue time
    access_token: Mapped[str] = mapped_column(String(64), unique=True) # secret in the receipt link
    pdf_path: Mapped[str | None] = mapped_column(String(300))          # file in Supabase Storage
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())