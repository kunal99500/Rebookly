"""Business logic for opening hours and slots."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.rules.catalog import BOOKING_WINDOW_HOURS
from app.clock import get_clock
from app.models import AvailabilityRule, Booking, Business, Service, Slot
from app.rules.scheduling import BusyPeriod, WeeklyHours, generate_slot_times, remove_busy
from app.schemas.schedule import AvailabilityIn
from app.services import audit


async def get_hours(session: AsyncSession, business: Business) -> list[AvailabilityRule]:
    result = await session.scalars(
        select(AvailabilityRule).where(AvailabilityRule.business_id == business.id)
        .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)
    )
    return list(result)


async def replace_hours(
    session: AsyncSession, business: Business, owner_id: uuid.UUID, data: AvailabilityIn
) -> list[AvailabilityRule]:
    """Replace the whole weekly schedule in one go. Existing slots and bookings are not touched."""
    await session.execute(delete(AvailabilityRule).where(AvailabilityRule.business_id == business.id))
    for h in data.hours:
        session.add(AvailabilityRule(business_id=business.id, weekday=h.weekday, start_time=h.start, end_time=h.end))
    audit.record(session, actor_type="owner", actor_id=owner_id, action="availability.updated",
                 business_id=business.id, details={"periods": len(data.hours)})
    await session.commit()
    return await get_hours(session, business)


async def generate_slots(session: AsyncSession, business: Business, owner_id: uuid.UUID, days: int) -> tuple[int, int]:
    """Create bookable slots for the next `days` days. Safe to run repeatedly: existing slots are kept."""
    rules = await get_hours(session, business)
    if not rules:
        raise HTTPException(status.HTTP_409_CONFLICT, "Set your opening hours first")
    services = list(await session.scalars(
        select(Service).where(Service.business_id == business.id, Service.is_active.is_(True))
    ))
    if not services:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add at least one service first")

    now = get_clock().now()
    today = now.astimezone(ZoneInfo(business.timezone)).date()
    hours = [WeeklyHours(r.weekday, r.start_time, r.end_time) for r in rules]

    created = 0
    for service in services:
        times = generate_slot_times(hours, service.duration_minutes, business.timezone, today, days, now)
        if not times:
            continue
        rows = [
            {"id": uuid.uuid4(), "business_id": business.id, "service_id": service.id,
             "starts_at": t.starts_at, "ends_at": t.ends_at, "capacity": service.capacity}
            for t in times
        ]
        result = await session.execute(
            insert(Slot).values(rows).on_conflict_do_nothing(constraint="uq_slots_service_start").returning(Slot.id)
        )
        created += len(result.all())

    audit.record(session, actor_type="owner", actor_id=owner_id, action="slots.generated",
                 business_id=business.id, details={"created": created, "days": days})
    await session.commit()
    return created, len(services)


async def list_slots(
    session: AsyncSession, business: Business, start: datetime, end: datetime, service_id: uuid.UUID | None = None
) -> list[Slot]:
    query = select(Slot).where(Slot.business_id == business.id, Slot.starts_at >= start, Slot.starts_at < end)
    if service_id is not None:
        query = query.where(Slot.service_id == service_id)
    return list(await session.scalars(query.order_by(Slot.starts_at)))


def is_bookable(slot: Slot, now: datetime) -> bool:
    return (
        not slot.is_blocked
        and slot.booked_count < slot.capacity
        and now < slot.starts_at <= now + timedelta(hours=BOOKING_WINDOW_HOURS)
    )


async def set_blocked(session: AsyncSession, slot: Slot, owner_id: uuid.UUID, blocked: bool) -> Slot:
    if blocked and slot.booked_count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This slot has bookings. Cancel or move them before blocking it.")
    if slot.is_blocked != blocked:
        slot.is_blocked = blocked
        audit.record(session, actor_type="owner", actor_id=owner_id,
                     action="slot.blocked" if blocked else "slot.unblocked",
                     business_id=slot.business_id, details={"slot_id": str(slot.id)})
        await session.commit()
        await session.refresh(slot)
    return slot


async def busy_periods(
    session: AsyncSession, business_id: uuid.UUID, start: datetime, end: datetime, now: datetime
) -> list[BusyPeriod]:
    """Times the provider is already taken: confirmed bookings, and bookings still being paid for."""
    rows = await session.execute(
        select(Booking.slot_id, Booking.starts_at, Booking.ends_at).where(
            Booking.business_id == business_id,
            Booking.starts_at < end,
            Booking.ends_at > start,
            or_(
                Booking.status == "confirmed",
                (Booking.status == "pending_payment") & (Booking.payment_expires_at > now),
            ),
        )
    )
    return [BusyPeriod(r.slot_id, r.starts_at, r.ends_at) for r in rows]


async def available_slots(session: AsyncSession, business: Business, service: Service, now: datetime) -> list[Slot]:
    """Slots a client can book right now for this service."""
    window_end = now + timedelta(hours=BOOKING_WINDOW_HOURS)
    candidates = list(await session.scalars(
        select(Slot).where(
            Slot.service_id == service.id,
            Slot.is_blocked.is_(False),
            Slot.booked_count < Slot.capacity,
            Slot.starts_at > now,
            Slot.starts_at <= window_end,
        ).order_by(Slot.starts_at)
    ))
    if not candidates:
        return []
    busy = await busy_periods(session, business.id, now, window_end + timedelta(days=1), now)
    return remove_busy(candidates, busy)