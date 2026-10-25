"""Photos of a business: one cover, a gallery, and optional photos per service."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKey, one_of

PHOTO_KINDS = ("cover", "gallery", "service")
MODERATION_STATUSES = ("approved", "flagged", "hidden")  # flagged/hidden photos are not shown publicly


class BusinessPhoto(UUIDPrimaryKey, Base):
    __tablename__ = "business_photos"
    __table_args__ = (
        CheckConstraint(one_of("kind", PHOTO_KINDS), name="kind_valid"),
        CheckConstraint(one_of("moderation_status", MODERATION_STATUSES), name="moderation_status_valid"),
        CheckConstraint("(kind = 'service') = (service_id IS NOT NULL)", name="service_photo_has_service"),
        Index("ix_business_photos_business", "business_id", "kind", "sort_order"),
        # Only one cover per business, and one photo per service.
        Index("uq_business_photos_one_cover", "business_id", unique=True, postgresql_where=text("kind = 'cover'")),
        Index("uq_business_photos_one_per_service", "service_id", unique=True,
              postgresql_where=text("kind = 'service'")),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(10))
    storage_path: Mapped[str] = mapped_column(String(300))
    thumb_path: Mapped[str] = mapped_column(String(300))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    alt_text: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # The owner confirmed this is a real, unaltered photo of their business (required to upload).
    attested_real_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Approved photos are public. Reported photos become "flagged" and are hidden until reviewed.
    moderation_status: Mapped[str] = mapped_column(String(10), default="approved", server_default="approved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())