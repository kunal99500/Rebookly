"""Client API: profile and bookings. Every route requires a signed-in client."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser
from app.config import get_settings
from app.db import get_session
from app.models import Booking, Business, Service,BookingItem
from app.rules.engine import Action, Event
from app.schemas.client import BookingCreate, BookingItemOut, BookingOut, BookingStarted, ProfileIn, ProfileOut
from app.schemas.outcome import CancelPreviewOut, DecisionOut, OutcomeOut
from app.security.links import checkout_signature
from app.security.phone import mask_phone
from app.services import bookings, clients, outcomes

from app.documents.issue import list_for_booking
from app.documents.schemas import DocumentLinkOut

router = APIRouter(prefix="/api/client", tags=["client"])


def _service(request: Request, name: str):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"{name} is not configured on the server")
    return value


@router.get("/profile", response_model=ProfileOut)
async def get_profile(
    request: Request, user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    client = await clients.require_client(session, user)
    phone = _service(request, "phones").reveal(client.phone_encrypted) if client.phone_encrypted else None
    return ProfileOut(name=client.name, phone_masked=mask_phone(phone) if phone else None)


@router.put("/profile", response_model=ProfileOut)
async def save_profile(
    data: ProfileIn,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Save the client's name. The phone number comes from their verified sign-in."""
    phones = _service(request, "phones")
    client = await clients.save_profile(session, user, data, phones, allow_dev_phone=get_settings().enable_dev_routes)
    return ProfileOut(name=client.name, phone_masked=mask_phone(phones.reveal(client.phone_encrypted)))


@router.post("/bookings", response_model=BookingStarted, status_code=status.HTTP_201_CREATED)
async def start_booking(
    data: BookingCreate,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Reserve the slot for 15 minutes and create the PayPal order. Open checkout_url to pay."""
    paypal = _service(request, "paypal")
    client = await clients.require_client(session, user)
    booking = await bookings.create_booking(session, client, data)
    await bookings.hold_payment(session, paypal, booking)
    settings = get_settings()
    signature = checkout_signature(settings.phone_hash_key.get_secret_value(), booking.id)
    return BookingStarted(
        booking_id=booking.id, status=booking.status, held_amount=booking.held_amount,
        currency=booking.currency, payment_expires_at=booking.payment_expires_at,
        checkout_url=f"{settings.backend_url}/checkout/{booking.id}?sig={signature}",
    )


async def _booking_out(session: AsyncSession, booking: Booking) -> BookingOut:
       business = await session.get(Business, booking.business_id)
       items = list(await session.scalars(
           select(BookingItem).where(BookingItem.booking_id == booking.id).order_by(BookingItem.position)))
       return BookingOut(
           id=booking.id, status=booking.status, business_name=business.name,
           service_name=" + ".join(i.name for i in items) or "Booking",
           items=[BookingItemOut(name=i.name, kind=i.kind, duration_minutes=i.duration_minutes, price=i.price)
                  for i in items],
           staff_name=await bookings.staff_name(session, booking),
           starts_at=booking.starts_at, ends_at=booking.ends_at, timezone=business.timezone,
           price=booking.price, held_amount=booking.held_amount, currency=booking.currency,
           payment_option=booking.payment_option, confirmation_number=booking.confirmation_number,
           attendee_name=booking.attendee_name,
       )


@router.get("/bookings", response_model=list[BookingOut])
async def my_bookings(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    client = await clients.require_client(session, user)
    rows = await session.scalars(
        select(Booking).where(Booking.client_id == client.id, Booking.status != "expired")
        .order_by(Booking.starts_at.desc())
    )
    return [await _booking_out(session, b) for b in rows]


async def _my_booking(session: AsyncSession, user: AuthUser, booking_id: uuid.UUID) -> Booking:
    client = await clients.require_client(session, user)
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id, Booking.client_id == client.id))
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


@router.get("/bookings/{booking_id}", response_model=BookingOut)
async def one_booking(
    booking_id: uuid.UUID, user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await _booking_out(session, await _my_booking(session, user, booking_id))


@router.get("/bookings/{booking_id}/cancel-preview", response_model=CancelPreviewOut)
async def cancel_preview(
    booking_id: uuid.UUID, user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """What would happen if you cancelled now. Nothing is changed."""
    booking = await _my_booking(session, user, booking_id)
    if booking.status != "confirmed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only confirmed bookings can be cancelled")
    result, payment = await outcomes.preview(session, booking, Event.CLIENT_CANCELLED)
    fee = result.amount if result.action == Action.CAPTURE else 0
    return CancelPreviewOut(fee=fee, released=payment.amount - fee, currency=payment.currency,
                            needs_owner_approval=result.needs_owner_approval, reason=result.reason)


@router.post("/bookings/{booking_id}/cancel", response_model=OutcomeOut)
async def cancel(
    booking_id: uuid.UUID, request: Request,
    user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session),
):
    """Cancel your booking. Any fee follows the policy you agreed to and is confirmed by the business."""
    booking = await _my_booking(session, user, booking_id)
    booking, decision = await outcomes.apply_event(
        session, _service(request, "paypal"), booking.id, Event.CLIENT_CANCELLED, "client", user.id)
    message = {
        "pending_approval": "Cancelled. The business will confirm whether a fee applies.",
        "executed": "Cancelled. Your hold has been released.",
    }.get(decision.status, "Cancelled.")
    return OutcomeOut(booking_status=booking.status, decision=DecisionOut.model_validate(decision), message=message)


@router.get("/bookings/{booking_id}/documents", response_model=list[DocumentLinkOut])
async def booking_documents(
    booking_id: uuid.UUID, user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Every confirmation, receipt and notice issued for this booking."""
    booking = await _my_booking(session, user, booking_id)
    return await list_for_booking(session, booking.id)