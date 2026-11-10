"""Available start times for any combination of services, for one staff member or "any available".

Loads hours, bookings and time off from the database, then hands everything to the pure rules
in app/rules/availability.py. Nothing here decides prices or money.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AvailabilityRule, Booking, Business, Service, Staff, StaffHours, StaffService, TimeOff
from app.rules.availability import (
    Interval, WeeklyPeriod, combine_staff, opening_intervals, start_times, subtract,
)
from app.rules.catalog import BOOKING_WINDOW_HOURS
from app.rules.pricing import ServiceLine, VisitError, VisitPlan, plan_visit

ACTIVE_BOOKING = or_(Booking.status == "confirmed", Booking.status == "pending_payment")


@dataclass(frozen=True)
class TimeOption:
    starts_at: datetime
    ends_at: datetime
    staff_ids: list[uuid.UUID]     # who is free then, in the business's preferred order


async def load_visit(session: AsyncSession, business: Business, service_ids: list[uuid.UUID]) -> tuple[VisitPlan, list[Service]]:
    """The chosen services as one visit (time, price, hold), or a clear error."""
    if not service_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose at least one service")
    rows = list(await session.scalars(select(Service).where(
        Service.id.in_(service_ids), Service.business_id == business.id, Service.is_active.is_(True),
    )))
    if len(rows) != len(set(service_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One of those services isn't available")
    if any(s.booking_mode != "appointment" for s in rows):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Classes are booked from their session times")
    by_id = {s.id: s for s in rows}
    lines = [
        ServiceLine(s.id, s.name, s.kind, s.duration_minutes, s.cleanup_minutes, s.price, s.deposit,
                    tuple(s.payment_options))
        for s in (by_id[sid] for sid in service_ids)
    ]
    try:
        return plan_visit(lines), rows
    except VisitError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))


async def eligible_staff(
    session: AsyncSession, business: Business, service_ids: list[uuid.UUID], staff_id: uuid.UUID | None,
) -> list[Staff]:
    """Active staff who can do every chosen service (or just the one the client picked)."""
    query = select(Staff).where(Staff.business_id == business.id, Staff.is_active.is_(True))
    if staff_id is not None:
        query = query.where(Staff.id == staff_id)
    staff = list(await session.scalars(query.order_by(Staff.sort_order, Staff.created_at)))
    if not staff:
        return []
    links = await session.execute(select(StaffService.staff_id, StaffService.service_id).where(
        StaffService.staff_id.in_([s.id for s in staff]), StaffService.service_id.in_(service_ids),
    ))
    can_do: dict[uuid.UUID, set] = {}
    for sid, svc in links:
        can_do.setdefault(sid, set()).add(svc)
    needed = set(service_ids)
    return [s for s in staff if can_do.get(s.id, set()) >= needed]


async def available_times(
    session: AsyncSession, business: Business, service_ids: list[uuid.UUID],
    staff_id: uuid.UUID | None, now: datetime,
) -> tuple[VisitPlan, list[Staff], list[TimeOption]]:
    plan, _ = await load_visit(session, business, service_ids)
    staff = await eligible_staff(session, business, service_ids, staff_id)
    if not staff:
        return plan, [], []

    tz = business.timezone
    earliest = now + timedelta(minutes=business.min_notice_minutes)
    latest_start = now + timedelta(hours=BOOKING_WINDOW_HOURS)
    first_day = now.astimezone(ZoneInfo(tz)).date()
    days = BOOKING_WINDOW_HOURS // 24 + 2
    window_end = latest_start + timedelta(minutes=plan.occupied_minutes)
    staff_ids = [s.id for s in staff]

    # Opening hours: each staff member's own hours, or the business's hours if they have none.
    business_hours = [WeeklyPeriod(r.weekday, r.start_time, r.end_time) for r in await session.scalars(
        select(AvailabilityRule).where(AvailabilityRule.business_id == business.id))]
    own_hours: dict[uuid.UUID, list[WeeklyPeriod]] = {}
    for h in await session.scalars(select(StaffHours).where(StaffHours.staff_id.in_(staff_ids))):
        own_hours.setdefault(h.staff_id, []).append(WeeklyPeriod(h.weekday, h.start_time, h.end_time))

    # Busy: active bookings (including cleanup) and time off, for the whole window.
    busy: dict[uuid.UUID, list[Interval]] = {sid: [] for sid in staff_ids}
    bookings = await session.execute(select(Booking.staff_id, Booking.starts_at, Booking.occupied_until).where(
        Booking.staff_id.in_(staff_ids), ACTIVE_BOOKING,
        Booking.starts_at < window_end, Booking.occupied_until > now,
    ))
    for sid, start, until in bookings:
        busy[sid].append(Interval(start, until))
    offs = await session.execute(select(TimeOff.staff_id, TimeOff.starts_at, TimeOff.ends_at).where(
        TimeOff.business_id == business.id, TimeOff.starts_at < window_end, TimeOff.ends_at > now,
        or_(TimeOff.staff_id.is_(None), TimeOff.staff_id.in_(staff_ids)),
    ))
    for sid, start, end in offs:
        for target in ([sid] if sid else staff_ids):   # no staff_id = the whole business is closed
            busy[target].append(Interval(start, end))

    visit = timedelta(minutes=plan.duration_minutes)
    occupied = timedelta(minutes=plan.occupied_minutes)
    step = timedelta(minutes=business.start_interval_minutes)
    per_staff = {}
    for s in staff:
        hours = own_hours.get(s.id) or business_hours
        free = subtract(opening_intervals(hours, tz, first_day, days), busy[s.id])
        per_staff[s.id] = start_times(free, visit, occupied, step, earliest, latest_start, tz)

    options = [
        TimeOption(start, start + visit, ids)
        for start, ids in combine_staff(per_staff).items()
    ]
    return plan, staff, options