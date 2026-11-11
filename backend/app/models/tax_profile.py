"""A business's tax details, as they appear on receipts. One per business.

Identity and bank verification are NOT stored here: the payment provider handles those.
"""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey, one_of

VERIFICATION_STATUSES = ("unverified", "format_valid", "verified", "not_found")


class BusinessTaxProfile(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "business_tax_profiles"
    __table_args__ = (
        CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code_format"),
        CheckConstraint("tax_rate IS NULL OR tax_rate BETWEEN 0 AND 100", name="tax_rate_range"),
        CheckConstraint("NOT tax_registered OR tax_rate IS NOT NULL", name="registered_has_rate"),
        CheckConstraint(one_of("verification_status", VERIFICATION_STATUSES), name="verification_status_valid"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    country_code: Mapped[str] = mapped_column(String(2))
    legal_name: Mapped[str | None] = mapped_column(String(160))          # as printed on receipts
    registered_address: Mapped[str | None] = mapped_column(String(300))
    region_code: Mapped[str | None] = mapped_column(String(10))           # e.g. India's GST state code "27"
    tax_registered: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    registration_type: Mapped[str | None] = mapped_column(String(20))     # gstin, vat, abn, gst_hst, ein, tax_id
    registration_number: Mapped[str | None] = mapped_column(String(30))   # stored normalized
    verification_status: Mapped[str] = mapped_column(String(12), default="unverified", server_default="unverified")
    tax_label: Mapped[str] = mapped_column(String(20))                    # GST, VAT, Sales tax
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))       # the rate the owner confirmed
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    fees_taxable: Mapped[bool | None] = mapped_column(Boolean)            # None = not decided (ask an accountant)