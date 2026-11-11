"""Client API: the waitlist. Join when a time you want is taken; book in one tap when it's offered."""
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser
from app.clock import get_clock
from app.db import get_session
from app.models import WaitlistEntry
from app.routers.client.bookings import _service, _start_checkout
from app.schemas.client import BookingCreate, BookingStarted, ClassBookingCreate
from app.schemas.waitlist import WaitlistJoin, WaitlistOut
from app.services import bookings, clients, waitlist

router = APIRouter(prefix="/api/client/waitlist", tags=["client: waitlist"])


class AcceptOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_option: Literal["deposit_held", "full_held"]


@router.post("", response_model=WaitlistOut, status_code=status.HTTP_201_CREATED)
async def join(data: WaitlistJoin, user: AuthUser = Depends(get_current_user),
               session: AsyncSession = Depends(get_session)):
    """Wait for a time: services + a day + a time window, or a full class session.

    If a matching time opens up, you're offered it (with an email if you've added one). The first to book gets it.
    """
    client = await clients.require_client(session, user)
    entry = await waitlist.join(session, client, data)
    return await waitlist.entry_out(session, entry)


@router.get("", response_model=list[WaitlistOut])
async def my_waitlist(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Your waitlist entries: offers first, then those still waiting, then recent ones."""
    client = await clients.require_client(session, user)
    since = (get_clock().now() - timedelta(days=7)).date()
    entries = await session.scalars(select(WaitlistEntry).where(
        WaitlistEntry.client_id == client.id, WaitlistEntry.wanted_date >= since).order_by(WaitlistEntry.wanted_date))
    order = {"offered": 0, "waiting": 1}
    return sorted([await waitlist.entry_out(session, e) for e in entries], key=lambda e: order.get(e.status, 2))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def leave(entry_id: uuid.UUID, user: AuthUser = Depends(get_current_user),
                session: AsyncSession = Depends(get_session)):
    await waitlist.leave(session, await clients.require_client(session, user), entry_id)


@router.post("/{entry_id}/accept", response_model=BookingStarted, status_code=status.HTTP_201_CREATED)
async def accept(entry_id: uuid.UUID, data: AcceptOffer, request: Request,
                 user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Book the offered time. It goes through the normal booking and checkout, with the same deposit and policy."""
    _service(request, "paypal")
    client = await clients.require_client(session, user)
    entry = await waitlist.accepted_entry(session, client, entry_id)
    try:
        if entry.slot_id is not None:
            booking = await bookings.create_class_booking(
                session, client, ClassBookingCreate(slot_id=entry.slot_id, payment_option=data.payment_option))
        else:
            booking = await bookings.create_booking(session, client, BookingCreate(
                service_ids=[uuid.UUID(s) for s in entry.service_ids], starts_at=entry.offered_starts_at,
                payment_option=data.payment_option))
    except HTTPException as err:
        if err.status_code == status.HTTP_409_CONFLICT:
            entry = await session.get(WaitlistEntry, entry_id)
            await waitlist.back_to_waiting(session, entry)
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Sorry, someone else just booked that time. You're still on the waitlist.")
        raise
    await waitlist.mark_booked(session, entry, booking)
    return await _start_checkout(request, session, booking)