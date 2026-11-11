"""Moving a confirmed booking to another time (same services, same hold, same policy)."""
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.documents.issue import issue_confirmation, issue_safely
from app.models import Booking, BookingItem, Business, Payment
from app.rules.rescheduling import reschedule_problem
from app.services import audit, availability


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


async def _hold(session: AsyncSession, booking: Booking) -> Payment:
    payment = await session.scalar(select(Payment).where(
        Payment.booking_id == booking.id, Payment.kind == "hold", Payment.status == "authorized"))
    if payment is None:
        raise _conflict("This booking has no active hold")
    return payment


async def _service_ids(session: AsyncSession, booking: Booking) -> list[uuid.UUID]:
    return list(await session.scalars(select(BookingItem.service_id).where(BookingItem.booking_id == booking.id)
                                      .order_by(BookingItem.position)))


async def options(
    session: AsyncSession, booking: Booking, day: date | None = None, staff_id: uuid.UUID | None = None,
) -> list[availability.TimeOption]:
    """Times this booking could move to (its own current time isn't counted as busy)."""
    now = get_clock().now()
    business = await session.get(Business, booking.business_id)
    payment = await _hold(session, booking)
    _, _, times = await availability.available_times(
        session, business, await _service_ids(session, booking), staff_id, now, ignore_booking_id=booking.id)
    tz = ZoneInfo(business.timezone)
    free_hours = int(booking.policy_snapshot.get("free_cancel_hours", 0))
    allowed = [
        t for t in times
        if reschedule_problem(now=now, current_start=booking.starts_at, new_start=t.starts_at,
                              free_cancel_hours=free_hours, honor_period_ends_at=payment.honor_period_ends_at) is None
    ]
    if day is not None:
        allowed = [t for t in allowed if t.starts_at.astimezone(tz).date() == day]
    return allowed


async def reschedule(
    session: AsyncSession, booking_id: uuid.UUID, new_start: datetime, staff_id: uuid.UUID | None,
    actor_type: str, actor_id: uuid.UUID | None,
) -> Booking:
    now = get_clock().now()
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status != "confirmed":
        raise _conflict("Only confirmed bookings can be moved")
    payment = await _hold(session, booking)
    problem = reschedule_problem(
        now=now, current_start=booking.starts_at, new_start=new_start,
        free_cancel_hours=int(booking.policy_snapshot.get("free_cancel_hours", 0)),
        honor_period_ends_at=payment.honor_period_ends_at)
    if problem:
        raise _conflict(problem)

    business = await session.get(Business, booking.business_id)
    _, staff, times = await availability.available_times(
        session, business, await _service_ids(session, booking), staff_id, now, ignore_booking_id=booking.id)
    match = next((t for t in times if t.starts_at == new_start), None)
    if match is None:
        raise _conflict("Sorry, that time isn't available. Please pick another.")
    # Keep the same person if they're free then; otherwise the first free person.
    chosen_id = booking.staff_id if booking.staff_id in match.staff_ids else match.staff_ids[0]
    chosen = next(s for s in staff if s.id == chosen_id)

    old_start = booking.starts_at
    visit = booking.ends_at - booking.starts_at
    occupied = booking.occupied_until - booking.starts_at
    booking.starts_at, booking.ends_at, booking.occupied_until = new_start, new_start + visit, new_start + occupied
    booking.staff_id, booking.location_id = chosen.id, chosen.location_id
    audit.record(session, actor_type=actor_type, actor_id=actor_id, action="booking.rescheduled",
                 business_id=booking.business_id, booking_id=booking.id,
                 details={"from": old_start.isoformat(), "to": new_start.isoformat(), "staff_id": str(chosen.id)})
    try:
        await session.flush()   # the database's overlap protection checks the new time here
    except IntegrityError:
        await session.rollback()
        raise _conflict("Sorry, that time was just taken. Please pick another.")
    await issue_safely(session, issue_confirmation(session, booking, replace=True))  # new confirmation, new time
    await session.commit()
    await session.refresh(booking)
    return booking