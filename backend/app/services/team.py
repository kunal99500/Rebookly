"""Staff, the services each one does, their own hours, and time off."""
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Business, Location, Service, Staff, StaffHours, StaffService, TimeOff
from app.schemas.schedule import WeeklyHoursIn
from app.schemas.team import StaffCreate, StaffHoursIn, StaffOut, StaffUpdate, TimeOffIn
from app.services import audit


# ---------- defaults for every business ----------

async def ensure_defaults(session: AsyncSession, business: Business) -> Staff:
    """Every business has a primary location and at least one staff member (the owner). Safe to call often."""
    location = await session.scalar(select(Location).where(
        Location.business_id == business.id, Location.is_primary.is_(True)))
    if location is None:
        location = Location(id=uuid.uuid4(), business_id=business.id, name="Main", is_primary=True)
        session.add(location)
        await session.flush()
    staff = await session.scalar(select(Staff).where(Staff.business_id == business.id).order_by(Staff.created_at))
    if staff is None:
        staff = Staff(id=uuid.uuid4(), business_id=business.id, location_id=location.id,
                      name=business.name[:80], auth_user_id=business.owner_user_id)
        session.add(staff)
        await session.flush()
        for service_id in await session.scalars(select(Service.id).where(Service.business_id == business.id)):
            session.add(StaffService(staff_id=staff.id, service_id=service_id))
    return staff


async def link_service_to_all_staff(session: AsyncSession, business: Business, service_id: uuid.UUID) -> None:
    """New services are offered by every active staff member until the owner says otherwise."""
    await ensure_defaults(session, business)
    staff_ids = list(await session.scalars(select(Staff.id).where(
        Staff.business_id == business.id, Staff.is_active.is_(True))))
    for sid in staff_ids:
        session.add(StaffService(staff_id=sid, service_id=service_id))


# ---------- reading ----------

async def _out(session: AsyncSession, staff: Staff) -> StaffOut:
    service_ids = list(await session.scalars(select(StaffService.service_id).where(StaffService.staff_id == staff.id)))
    hours = list(await session.scalars(select(StaffHours).where(StaffHours.staff_id == staff.id)
                                       .order_by(StaffHours.weekday, StaffHours.start_time)))
    return StaffOut(
        id=staff.id, name=staff.name, is_active=staff.is_active, sort_order=staff.sort_order,
        service_ids=service_ids, uses_business_hours=not hours,
        hours=[WeeklyHoursIn(weekday=h.weekday, start=h.start_time, end=h.end_time) for h in hours],
    )


async def list_team(session: AsyncSession, business: Business) -> list[StaffOut]:
    await ensure_defaults(session, business)
    await session.commit()
    staff = await session.scalars(select(Staff).where(Staff.business_id == business.id)
                                  .order_by(Staff.sort_order, Staff.created_at))
    return [await _out(session, s) for s in staff]


async def get_staff(session: AsyncSession, business: Business, staff_id: uuid.UUID) -> Staff:
    staff = await session.scalar(select(Staff).where(Staff.id == staff_id, Staff.business_id == business.id))
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
    return staff


# ---------- changing ----------

async def _check_services(session: AsyncSession, business: Business, service_ids: list[uuid.UUID] | None) -> list[uuid.UUID]:
    if service_ids is None:  # default: every active service
        return list(await session.scalars(select(Service.id).where(
            Service.business_id == business.id, Service.is_active.is_(True))))
    unique = list(dict.fromkeys(service_ids))
    found = await session.scalar(select(func.count()).select_from(Service).where(
        Service.id.in_(unique), Service.business_id == business.id))
    if found != len(unique):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One of those services doesn't exist")
    return unique


async def _set_services(session: AsyncSession, staff: Staff, service_ids: list[uuid.UUID]) -> None:
    await session.execute(delete(StaffService).where(StaffService.staff_id == staff.id))
    for sid in service_ids:
        session.add(StaffService(staff_id=staff.id, service_id=sid))


async def create_staff(session: AsyncSession, business: Business, owner_id: uuid.UUID, data: StaffCreate) -> StaffOut:
    default = await ensure_defaults(session, business)
    service_ids = await _check_services(session, business, data.service_ids)
    staff = Staff(id=uuid.uuid4(), business_id=business.id, location_id=default.location_id,
                  name=data.name, sort_order=data.sort_order)
    session.add(staff)
    await session.flush()
    await _set_services(session, staff, service_ids)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="staff.created",
                 business_id=business.id, details={"staff_id": str(staff.id)})
    await session.commit()
    return await _out(session, staff)


async def _upcoming_bookings(session: AsyncSession, staff_id: uuid.UUID, now: datetime,
                             starts: datetime | None = None, ends: datetime | None = None) -> int:
    query = select(func.count()).select_from(Booking).where(
        Booking.staff_id == staff_id, Booking.status == "confirmed", Booking.starts_at > now)
    if starts is not None:
        query = query.where(Booking.starts_at < ends, Booking.occupied_until > starts)
    return await session.scalar(query)


async def update_staff(session: AsyncSession, business: Business, staff: Staff, owner_id: uuid.UUID,
                       data: StaffUpdate, now: datetime) -> StaffOut:
    changes = data.model_dump(exclude_unset=True)
    if changes.get("is_active") is False and staff.is_active:
        if await _upcoming_bookings(session, staff.id, now):
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "This person has upcoming bookings. Move or cancel them first.")
        others = await session.scalar(select(func.count()).select_from(Staff).where(
            Staff.business_id == business.id, Staff.is_active.is_(True), Staff.id != staff.id))
        if not others:
            raise HTTPException(status.HTTP_409_CONFLICT, "A business needs at least one active staff member")
    if "service_ids" in changes:
        await _set_services(session, staff, await _check_services(session, business, changes.pop("service_ids")))
    for field, value in changes.items():
        setattr(staff, field, value)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="staff.updated", business_id=business.id,
                 details={"staff_id": str(staff.id), "fields": sorted(data.model_dump(exclude_unset=True))})
    await session.commit()
    await session.refresh(staff)
    return await _out(session, staff)


async def set_hours(session: AsyncSession, business: Business, staff: Staff, owner_id: uuid.UUID,
                    data: StaffHoursIn) -> StaffOut:
    """Replace this person's weekly hours. An empty list means they follow the business's hours."""
    await session.execute(delete(StaffHours).where(StaffHours.staff_id == staff.id))
    for h in data.hours:
        session.add(StaffHours(staff_id=staff.id, weekday=h.weekday, start_time=h.start, end_time=h.end))
    audit.record(session, actor_type="owner", actor_id=owner_id, action="staff.hours_updated",
                 business_id=business.id, details={"staff_id": str(staff.id), "periods": len(data.hours)})
    await session.commit()
    return await _out(session, staff)


async def add_time_off(session: AsyncSession, business: Business, owner_id: uuid.UUID,
                       data: TimeOffIn, now: datetime) -> tuple[TimeOff, int]:
    staff_ids = [data.staff_id] if data.staff_id else list(await session.scalars(
        select(Staff.id).where(Staff.business_id == business.id)))
    if data.staff_id:
        await get_staff(session, business, data.staff_id)
    entry = TimeOff(business_id=business.id, staff_id=data.staff_id,
                    starts_at=data.starts_at, ends_at=data.ends_at, reason=data.reason)
    session.add(entry)
    affected = 0
    for sid in staff_ids:
        affected += await _upcoming_bookings(session, sid, now, data.starts_at, data.ends_at)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="time_off.added", business_id=business.id,
                 details={"staff_id": str(data.staff_id) if data.staff_id else None, "affected_bookings": affected})
    await session.commit()
    await session.refresh(entry)
    return entry, affected


async def list_time_off(session: AsyncSession, business: Business, start: datetime, end: datetime) -> list[TimeOff]:
    return list(await session.scalars(select(TimeOff).where(
        TimeOff.business_id == business.id, TimeOff.ends_at > start, TimeOff.starts_at < end,
    ).order_by(TimeOff.starts_at)))


async def delete_time_off(session: AsyncSession, business: Business, owner_id: uuid.UUID, time_off_id: uuid.UUID) -> None:
    entry = await session.scalar(select(TimeOff).where(TimeOff.id == time_off_id, TimeOff.business_id == business.id))
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Time off not found")
    await session.delete(entry)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="time_off.removed",
                 business_id=business.id, details={"time_off_id": str(time_off_id)})
    await session.commit()