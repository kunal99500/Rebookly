"""Release the seats of bookings whose 15-minute payment window passed without payment."""
from sqlalchemy import select

from app.clock import get_clock
from app.db import session_scope
from app.models import Booking
from app.services import bookings


async def run() -> int:
    now = get_clock().now()
    async with session_scope() as session:
        ids = list(await session.scalars(
            select(Booking.id).where(Booking.status == "pending_payment", Booking.payment_expires_at < now).limit(200)
        ))
    released = 0
    for booking_id in ids:
        async with session_scope() as session:
            # SKIP LOCKED: if another server is handling this booking right now, leave it to them.
            booking = await session.scalar(
                select(Booking).where(Booking.id == booking_id, Booking.status == "pending_payment")
                .with_for_update(skip_locked=True)
            )
            if booking is not None:
                await bookings.release_seat(session, booking, "payment_window_expired")
                released += 1
    return released