"""Saved versions of a business's cancellation policy. Rows are never edited; changes create a new version."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import UUIDPrimaryKey


class BusinessPolicy(UUIDPrimaryKey, Base):
    __tablename__ = "business_policies"
    __table_args__ = (
        UniqueConstraint("business_id", "version", name="uq_business_policies_business_version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)            # the owner's own words
    rules: Mapped[dict] = mapped_column(JSONB)             # structured rules, exactly Policy.to_dict()
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # set when the owner confirms
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    business: Mapped["Business"] = relationship(back_populates="policies")