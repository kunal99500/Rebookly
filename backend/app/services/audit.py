"""Adds entries to the permanent audit log. Saved together with the change it describes."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


def record(
    session: AsyncSession,
    *,
    actor_type: str,
    action: str,
    actor_id: uuid.UUID | None = None,
    business_id: uuid.UUID | None = None,
    booking_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> None:
    """Never put secrets, full phone numbers or message contents in details."""
    session.add(AuditEvent(
        actor_type=actor_type, action=action, actor_id=actor_id,
        business_id=business_id, booking_id=booking_id, details=details or {},
    ))