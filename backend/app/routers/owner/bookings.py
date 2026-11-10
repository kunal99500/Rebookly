"""Owner API: see bookings, check clients in, mark no-shows, and cancel."""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.clock import get_clock
from app.db import get_session
from app.models import Booking, Business, Client, Decision, Payment, Staff
from app.routers.owner.deps import get_owned_business, get_owner, get_paypal
from app.rules.engine import Event
from app.rules.outcomes import can_check_in, masked_last4
from app.schemas.outcome import CheckInIn, DecisionOut, OutcomeOut, OwnerBookingOut
from app.services import outcomes
from app.services import bookings as booking_service
from app.documents.issue import list_for_booking
from app.documents.schemas import DocumentLinkOut

router = APIRouter(prefix="/api/owner/businesses/{business_id}", tags=["owner: bookings"])

MESSAGES = {
    "pending_approval": "A fee is waiting for your approval.",
    "executed": "Done. The hold has been settled.",
    "waived": "Done. No fee was charged.",
    "failed": "PayPal couldn't complete this. You can try again from your approvals.",
}


async def _business_booking(session: AsyncSession, business: Business, booking_id: uuid.UUID) -> Booking:
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id, Booking.business_id == business.id))
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


def _outcome(booking: Booking, decision: Decision) -> OutcomeOut:
    return OutcomeOut(booking_status=booking.status, decision=DecisionOut.model_validate(decision),
                      message=MESSAGES.get(decision.status, "Saved."))


# ---------- bookings ----------

@router.get("/bookings", response_model=list[OwnerBookingOut])
async def list_bookings(
       start: datetime | None = Query(default=None, description="Defaults to the start of today (UTC)"),
       days: int = Query(default=7, ge=1, le=31),
       business: Business = Depends(get_owned_business),
       session: AsyncSession = Depends(get_session),
   ):
       if start is not None and start.tzinfo is None:
           raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "start must include a time zone, e.g. ...Z")
       start = start or get_clock().now().replace(hour=0, minute=0, second=0, microsecond=0)
       rows = (await session.execute(
           select(Booking, Client, Payment, Staff.name)
           .join(Client, Client.id == Booking.client_id)
           .outerjoin(Payment, (Payment.booking_id == Booking.id) & (Payment.kind == "hold"))
           .outerjoin(Staff, Staff.id == Booking.staff_id)
           .where(Booking.business_id == business.id, Booking.status != "expired",
                  Booking.starts_at >= start, Booking.starts_at < start + timedelta(days=days))
           .order_by(Booking.starts_at)
       )).all()
       summaries = await booking_service.visit_summaries(session, [b.id for b, *_ in rows])
       return [
           OwnerBookingOut(
               id=b.id, status=b.status, service_name=summaries.get(b.id, ""), staff_name=staff_name,
               starts_at=b.starts_at, ends_at=b.ends_at,
               client_name=c.name, client_phone=masked_last4(c.phone_last4), attendee_name=b.attendee_name,
               held_amount=b.held_amount, currency=b.currency, payment_option=b.payment_option,
               payment_status=p.status if p else None, confirmation_number=b.confirmation_number,
               checked_in_at=b.checked_in_at,
           )
           for b, c, p, staff_name in rows
       ]

@router.post("/check-in", response_model=OutcomeOut)
async def check_in(
    data: CheckInIn, request: Request,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Scan the client's QR code. Marks them attended and applies the hold to the price."""
    booking = await session.scalar(select(Booking).where(
        Booking.check_in_token == data.token, Booking.business_id == business.id))
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This code isn't for a booking at your business")
    if not can_check_in(booking.starts_at, booking.ends_at, get_clock().now()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Check-in opens an hour before the appointment")
    booking, decision = await outcomes.apply_event(session, get_paypal(request), booking.id, Event.ATTENDED, "owner", owner.id)
    return _outcome(booking, decision)


@router.post("/bookings/{booking_id}/no-show", response_model=OutcomeOut)
async def mark_no_show(
    booking_id: uuid.UUID, request: Request,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Mark a client as not attending. Only possible after the grace period; the fee waits for your approval."""
    booking = await _business_booking(session, business, booking_id)
    booking, decision = await outcomes.apply_event(session, get_paypal(request), booking.id, Event.NO_SHOW, "owner", owner.id)
    return _outcome(booking, decision)


@router.post("/bookings/{booking_id}/cancel", response_model=OutcomeOut)
async def cancel_booking(
    booking_id: uuid.UUID, request: Request,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Cancel on the client's behalf as the business. The hold is always released in full."""
    booking = await _business_booking(session, business, booking_id)
    booking, decision = await outcomes.apply_event(
        session, get_paypal(request), booking.id, Event.OWNER_CANCELLED, "owner", owner.id)
    return _outcome(booking, decision)

@router.get("/bookings/{booking_id}/documents", response_model=list[DocumentLinkOut])
async def booking_documents(
    booking_id: uuid.UUID,
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
):
    """Every confirmation, receipt and notice issued for this booking."""
    booking = await _business_booking(session, business, booking_id)
    return await list_for_booking(session, booking.id)