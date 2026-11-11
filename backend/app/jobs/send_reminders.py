"""Queue appointment reminders (the outbox makes sure each one is sent only once)."""
from datetime import timedelta

from sqlalchemy import select

from app.clock import get_clock
from app.db import session_scope
from app.models import Booking
from app.notifications import booking_messages
from app.notifications.rules import reminder_due


async def run() -> int:
    now = get_clock().now()
    queued = 0
    async with session_scope() as session:
        upcoming = list(await session.scalars(select(Booking).where(
            Booking.status == "confirmed", Booking.starts_at > now, Booking.starts_at <= now + timedelta(hours=25))))
        for booking in upcoming:
            kind = reminder_due(starts_at=booking.starts_at, booked_at=booking.created_at, now=now)
            if kind:
                await booking_messages.reminder(session, booking, kind)
                queued += 1
        await session.commit()
    return queued