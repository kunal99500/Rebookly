"""Owner API: staff, the services each one does, their hours, and time off."""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.clock import get_clock
from app.db import get_session
from app.models import Business
from app.routers.owner.deps import get_owned_business, get_owner
from app.schemas.team import (
    StaffCreate, StaffHoursIn, StaffOut, StaffUpdate, TimeOffCreated, TimeOffIn, TimeOffOut,
)
from app.services import team

router = APIRouter(prefix="/api/owner/businesses/{business_id}", tags=["owner: team"])


@router.get("/team", response_model=list[StaffOut])
async def list_team(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    """Everyone who performs services. Every business starts with one: the owner."""
    return await team.list_team(session, business)


@router.post("/team", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
async def add_staff(
    data: StaffCreate,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Add a staff member. Without service_ids they offer every service."""
    return await team.create_staff(session, business, owner.id, data)


@router.patch("/team/{staff_id}", response_model=StaffOut)
async def update_staff(
    staff_id: uuid.UUID, data: StaffUpdate,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Rename, change their services, reorder, or deactivate (only without upcoming bookings)."""
    staff = await team.get_staff(session, business, staff_id)
    return await team.update_staff(session, business, staff, owner.id, data, get_clock().now())


@router.put("/team/{staff_id}/hours", response_model=StaffOut)
async def set_staff_hours(
    staff_id: uuid.UUID, data: StaffHoursIn,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Their own weekly hours, in local time. Send an empty list to follow the business's opening hours."""
    staff = await team.get_staff(session, business, staff_id)
    return await team.set_hours(session, business, staff, owner.id, data)


@router.post("/time-off", response_model=TimeOffCreated, status_code=status.HTTP_201_CREATED)
async def add_time_off(
    data: TimeOffIn,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """A break or day off for one person, or (no staff_id) the whole business.

    Existing bookings aren't touched; affected_bookings tells you how many to move or cancel.
    """
    entry, affected = await team.add_time_off(session, business, owner.id, data, get_clock().now())
    return TimeOffCreated(time_off=TimeOffOut.model_validate(entry), affected_bookings=affected)


@router.get("/time-off", response_model=list[TimeOffOut])
async def list_time_off(
    start: datetime | None = Query(default=None, description="Defaults to now"),
    days: int = Query(default=30, ge=1, le=366),
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
):
    if start is not None and start.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "start must include a time zone, e.g. ...Z")
    start = start or get_clock().now()
    return await team.list_time_off(session, business, start, start + timedelta(days=days))


@router.delete("/time-off/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_time_off(
    time_off_id: uuid.UUID,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    await team.delete_time_off(session, business, owner.id, time_off_id)