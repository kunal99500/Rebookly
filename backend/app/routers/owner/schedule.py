"""Owner API: weekly opening hours and bookable slots."""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.clock import get_clock
from app.db import get_session
from app.models import Business, Slot
from app.routers.owner.deps import get_owned_business, get_owner
from app.schemas.schedule import AvailabilityIn, AvailabilityOut, GenerateSlotsOut, SlotOut, SlotUpdate, WeeklyHoursIn
from app.services import schedule

router = APIRouter(prefix="/api/owner/businesses/{business_id}", tags=["owner: schedule"])


def _hours_out(business: Business, rules) -> AvailabilityOut:
    return AvailabilityOut(
        timezone=business.timezone,
        hours=[WeeklyHoursIn(weekday=r.weekday, start=r.start_time, end=r.end_time) for r in rules],
    )


def _slot_out(slot: Slot, now: datetime) -> SlotOut:
    out = SlotOut.model_validate(slot)
    out.bookable = schedule.is_bookable(slot, now)
    return out


@router.get("/availability", response_model=AvailabilityOut)
async def get_availability(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    return _hours_out(business, await schedule.get_hours(session, business))


@router.put("/availability", response_model=AvailabilityOut)
async def set_availability(
    data: AvailabilityIn,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Replace the weekly opening hours. Times are local to the business's time zone."""
    return _hours_out(business, await schedule.replace_hours(session, business, owner.id, data))


@router.post("/slots/generate", response_model=GenerateSlotsOut)
async def generate_slots(
    days: int = Query(default=7, ge=1, le=14),
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Create bookable slots from the opening hours. Safe to repeat: existing slots are kept."""
    created, services = await schedule.generate_slots(session, business, owner.id, days)
    return GenerateSlotsOut(created=created, services=services, days=days)


@router.get("/slots", response_model=list[SlotOut])
async def list_slots(
    start: datetime | None = Query(default=None, description="Defaults to now"),
    days: int = Query(default=7, ge=1, le=14),
    service_id: uuid.UUID | None = None,
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
):
    now = get_clock().now()
    if start is not None and start.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "start must include a time zone, e.g. ...Z")
    start = start or now
    slots = await schedule.list_slots(session, business, start, start + timedelta(days=days), service_id)
    return [_slot_out(s, now) for s in slots]


@router.patch("/slots/{slot_id}", response_model=SlotOut)
async def update_slot(
    slot_id: uuid.UUID,
    data: SlotUpdate,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Block or unblock one slot (e.g. a dentist appointment). Slots with bookings can't be blocked."""
    slot = await session.scalar(select(Slot).where(Slot.id == slot_id, Slot.business_id == business.id))
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")
    slot = await schedule.set_blocked(session, slot, owner.id, data.is_blocked)
    return _slot_out(slot, get_clock().now())