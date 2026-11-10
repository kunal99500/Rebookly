"""Things only one booking can use at a time: chairs, rooms, courts, machines.

The table exists now so the structure is ready; resource-aware scheduling is added in a later stage.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class Resource(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "resources"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))          # "Room 2", "Chair 3"
    kind: Mapped[str] = mapped_column(String(40))          # "treatment_room", "chair"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))