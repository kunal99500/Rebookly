"""The checkout page where a client approves the PayPal hold, with PayPal or a card.

Opened from the app via the signed checkout_url. The signature proves the link came from us
for this exact booking, so no sign-in is needed on this page.
"""
import uuid
from datetime import timedelta
from pathlib import Path


from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Booking, Business, Payment, Service
from app.rules.policy_text import policy_summary
from app.rules.engine import Policy
from app.security.links import verify_checkout_signature
from app.services import bookings
from app.rules.formatting import local_time, money

router = APIRouter(tags=["checkout"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

OPTION_LABELS = {"deposit_held": "Deposit", "full_held": "Full amount"}



async def _signed_booking(booking_id: uuid.UUID, sig: str, session: AsyncSession) -> Booking:
    secret = get_settings().phone_hash_key.get_secret_value()
    booking = await session.get(Booking, booking_id)
    if booking is None or not verify_checkout_signature(secret, booking_id, sig):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Checkout link not found")
    return booking


@router.get("/checkout/{booking_id}", response_class=HTMLResponse, include_in_schema=False)
async def checkout_page(
    booking_id: uuid.UUID, request: Request, sig: str = Query(max_length=80),
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    booking = await _signed_booking(booking_id, sig, session)
    business = await session.get(Business, booking.business_id)
    summary = (await bookings.visit_summaries(session, [booking.id])).get(booking.id, "Booking")
    staff = await bookings.staff_name(session, booking)
    duration = int((booking.ends_at - booking.starts_at).total_seconds() // 60)
    payment = await session.scalar(select(Payment).where(Payment.booking_id == booking.id, Payment.kind == "hold"))

    policy = Policy.from_dict({**booking.policy_snapshot, "version": booking.policy_version})
    free_until = booking.starts_at - timedelta(hours=policy.free_cancel_hours)
    return templates.TemplateResponse(request, "checkout/booking_checkout.html", {
        "booking": booking,
        "business_name": business.name,
        "service_name": f"{summary} with {staff}" if staff else summary,
        "duration": duration,
        "when": local_time(booking.starts_at, business.timezone),
        "free_until": local_time(free_until, business.timezone) if policy.free_cancel_hours else None,
        "held_text": money(booking.held_amount, booking.currency),
        "price_text": money(booking.price, booking.currency),
        "due_after_text": money(booking.price - booking.held_amount, booking.currency),
        "zero_text": money(0, booking.currency),
        "timezone": business.timezone,
        "option_label": OPTION_LABELS[booking.payment_option],
        "policy_lines": policy_summary(policy),
        "order_id": payment.paypal_order_id if payment else None,
        "paypal_client_id": settings.paypal_client_id,
        "sig": sig,
        "frontend_url": settings.frontend_url,
    })


@router.post("/api/checkout/{booking_id}/authorize", include_in_schema=False)
async def authorize(
    booking_id: uuid.UUID, request: Request, sig: str = Query(max_length=80),
    session: AsyncSession = Depends(get_session),
):
    booking = await _signed_booking(booking_id, sig, session)
    paypal = getattr(request.app.state, "paypal", None)
    if paypal is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Payments are not available right now")
    booking = await bookings.authorize_hold(session, paypal, booking)
    return {"status": booking.status, "confirmation_number": booking.confirmation_number}