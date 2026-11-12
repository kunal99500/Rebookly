"""Owner API: move a client's booking (e.g. a staff member is ill). The client is told and may cancel free."""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Booking, Business
from app.routers.owner.deps import get_owned_business, get_owner
from app.schemas.client import RescheduleIn, RescheduleOption
from app.services import bookings, rescheduling

router = APIRouter(prefix="/api/owner/businesses/{business_id}/bookings/{booking_id}", tags=["owner: bookings"])


class OwnerMoveOut(BaseModel):
    booking_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    staff_name: str | None
    note: str = "The client has been told, and may cancel this booking without a fee."


async def _booking(session: AsyncSession, business: Business, booking_id: uuid.UUID) -> Booking:
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id, Booking.business_id == business.id))
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only confirmed bookings can be moved")
    return booking


@router.get("/reschedule-options", response_model=list[RescheduleOption])
async def options(booking_id: uuid.UUID, day: date | None = Query(default=None), staff_id: uuid.UUID | None = None,
                  business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    """Times this booking can move to (owners can move it any time before it starts)."""
    booking = await _booking(session, business, booking_id)
    times = await rescheduling.options(session, booking, day, staff_id, by_owner=True)
    return [RescheduleOption(starts_at=t.starts_at, ends_at=t.ends_at) for t in times]


@router.post("/reschedule", response_model=OwnerMoveOut)
async def reschedule(booking_id: uuid.UUID, data: RescheduleIn, business: Business = Depends(get_owned_business),
                     owner: AuthUser = Depends(get_owner), session: AsyncSession = Depends(get_session)):
    """Move the booking. Same services, deposit and policy; a new confirmation; the client is emailed."""
    booking = await _booking(session, business, booking_id)
    moved = await rescheduling.reschedule(session, booking.id, data.starts_at, data.staff_id, "owner", owner.id)
    return OwnerMoveOut(booking_id=moved.id, starts_at=moved.starts_at, ends_at=moved.ends_at,
                        staff_name=await bookings.staff_name(session, moved))