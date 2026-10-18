"""Shared building blocks for every table."""
import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKey:
    """A random, unguessable ID for each row (instead of 1, 2, 3...)."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"), sort_order=-100,
    )


class Timestamps:
    """When the row was created and last changed, always with a time zone."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), sort_order=100)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), sort_order=101
    )


def one_of(column: str, values: Iterable[str]) -> str:
    """Build a check rule like: status IN ('draft', 'live')."""
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({allowed})"