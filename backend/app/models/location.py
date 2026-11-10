"""A branch of a business. Every business has one primary location; chains can have several later."""
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class Location(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "locations"
    __table_args__ = (
        Index("uq_locations_one_primary", "business_id", unique=True, postgresql_where=text("is_primary")),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))