"""Writing messages to the outbox. Called inside the same transaction as the change they describe."""
import logging
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.models import Notification

logger = logging.getLogger("rebookly.notifications")


async def enqueue(
    session: AsyncSession, *, kind: str, to_address: str, recipient_type: str, payload: dict, dedupe_key: str,
    business_id: uuid.UUID | None = None, booking_id: uuid.UUID | None = None, channel: str = "email",
) -> None:
    """Add a message. If the same dedupe_key was already added, nothing happens (no duplicates, ever)."""
    await session.execute(
        insert(Notification).values(
            id=uuid.uuid4(), dedupe_key=dedupe_key[:200], business_id=business_id, booking_id=booking_id,
            channel=channel, recipient_type=recipient_type, to_address=to_address, kind=kind,
            payload=payload, status="pending", attempts=0, next_attempt_at=get_clock().now(),
        ).on_conflict_do_nothing(index_elements=["dedupe_key"])
    )


async def notify_safely(session: AsyncSession, creating) -> None:
    """Queue messages inside a savepoint: if that fails, the booking or payment change is still saved."""
    try:
        async with session.begin_nested():
            await creating
    except Exception:
        logger.exception("Couldn't queue a notification")