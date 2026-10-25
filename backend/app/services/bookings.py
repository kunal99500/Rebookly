"""Creating bookings and placing their PayPal holds.

Order of work when a client books:
  1. Lock the business briefly, check everything, take the seat, save a pending booking.  (one transaction)
  2. Create the PayPal order for the hold.                                                (outside the lock)
  3. The client approves on the checkout page; we authorize, and the booking is confirmed.
If anything fails after step 1, the seat is released.
"""
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.rules.booking import (
    MAX_ACTIVE_BOOKINGS_PER_BUSINESS, PAYMENT_WINDOW_MINUTES, hold_amount,
    new_check_in_token, new_confirmation_number,
)
from app.clock import get_clock
from app.models import Booking, Business, BusinessPolicy, Client, Payment, Service, Slot
from app.payments.paypal import PayPalClient, PayPalError
from app.schemas.client import BookingCreate
from app.services import audit, schedule

HONOR_PERIOD = timedelta(days=3)
ACTIVE = ("pending_payment", "confirmed")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


async def create_booking(session: AsyncSession, client: Client, data: BookingCreate) -> Booking:
    """Step 1: reserve the seat and save a pending booking. No PayPal yet."""
    now = get_clock().now()
    slot = await session.get(Slot, data.slot_id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That time isn't available")
    service = await session.get(Service, slot.service_id)
    business = await session.get(Business, slot.business_id)

    # Lock this business's row until we commit, so two bookings for overlapping times
    # can't both pass the checks below at the same moment.
    await session.execute(select(Business.id).where(Business.id == business.id).with_for_update())

    if business.status != "live" or not service.is_active:
        raise _conflict("This business isn't taking bookings right now")
    if data.payment_option not in service.payment_options:
        raise _conflict("That payment option isn't offered for this service")
    if not schedule.is_bookable(slot, now):
        raise _conflict("Sorry, that time was just taken or is no longer available")

    busy = await schedule.busy_periods(session, business.id, slot.starts_at, slot.ends_at, now)
    if any(b.slot_id != slot.id for b in busy):
        raise _conflict("Sorry, that time was just taken")

    active = await session.scalar(select(func.count()).select_from(Booking).where(
        Booking.client_id == client.id, Booking.business_id == business.id,
        Booking.status.in_(ACTIVE), Booking.starts_at > now,
    ))
    if active >= MAX_ACTIVE_BOOKINGS_PER_BUSINESS:
        raise _conflict(f"You can have up to {MAX_ACTIVE_BOOKINGS_PER_BUSINESS} upcoming bookings here")

    # Take the seat atomically: succeeds only if a seat is still free.
    taken = await session.execute(
        update(Slot)
        .where(Slot.id == slot.id, Slot.booked_count < Slot.capacity, Slot.is_blocked.is_(False))
        .values(booked_count=Slot.booked_count + 1)
        .returning(Slot.id)
    )
    if taken.first() is None:
        raise _conflict("Sorry, that time was just taken")

    policy = await session.scalar(select(BusinessPolicy).where(
        BusinessPolicy.business_id == business.id, BusinessPolicy.version == business.current_policy_version,
    ))
    booking = Booking(
        id=uuid.uuid4(),
        business_id=business.id, service_id=service.id, slot_id=slot.id, client_id=client.id,
        attendee_name=data.attendee_name,
        status="pending_payment",
        payment_option=data.payment_option,
        price=service.price,
        held_amount=hold_amount(service.price, service.deposit, data.payment_option),
        currency=business.currency,
        policy_version=policy.version,
        policy_snapshot=service.policy_override or policy.rules,  # the exact rules this client agrees to
        starts_at=slot.starts_at, ends_at=slot.ends_at,
        payment_expires_at=now + timedelta(minutes=PAYMENT_WINDOW_MINUTES),
        check_in_token=new_check_in_token(),
    )
    session.add(booking)
    audit.record(session, actor_type="client", actor_id=client.auth_user_id, action="booking.started",
                 business_id=business.id, booking_id=booking.id,
                 details={"slot_id": str(slot.id), "held_amount": str(booking.held_amount)})
    await session.commit()
    await session.refresh(booking)
    return booking


async def release_seat(session: AsyncSession, booking: Booking, reason: str) -> None:
    """Give the seat back and mark a booking that never got paid as expired."""
    if booking.status != "pending_payment":
        return
    booking.status = "expired"
    await session.execute(
        update(Slot).where(Slot.id == booking.slot_id, Slot.booked_count > 0)
        .values(booked_count=Slot.booked_count - 1)
    )
    audit.record(session, actor_type="system", action="booking.expired",
                 business_id=booking.business_id, booking_id=booking.id, details={"reason": reason})
    await session.commit()


async def hold_payment(session: AsyncSession, paypal: PayPalClient, booking: Booking) -> Payment:
    """Step 2: create the PayPal order for this booking's hold (or reuse the one already created)."""
    existing = await session.scalar(select(Payment).where(Payment.booking_id == booking.id, Payment.kind == "hold"))
    if existing is not None:
        return existing

    business = await session.get(Business, booking.business_id)
    service = await session.get(Service, booking.service_id)
    try:
        order = await paypal.create_order(
            amount=booking.held_amount,
            currency=booking.currency,
            reference_id=str(booking.id),
            description=f"{business.name}: {service.name} (deposit hold)",
            payee_merchant_id=business.paypal_merchant_id,
            request_id=f"hold-{booking.id}",  # stable: a retry returns the same order
        )
    except PayPalError:
        await release_seat(session, booking, "paypal_order_failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal is unavailable right now. Please try again.")

    payment = Payment(
        booking_id=booking.id, kind="hold", status="created",
        amount=booking.held_amount, currency=booking.currency,
        paypal_order_id=order["id"], payee_merchant_id=business.paypal_merchant_id,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


def _parse_paypal_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


async def authorize_hold(session: AsyncSession, paypal: PayPalClient, booking: Booking) -> Booking:
    """Step 3: after the client approves on PayPal, place the hold and confirm the booking."""
    if booking.status == "confirmed":
        return booking  # already done (e.g. the page was submitted twice)
    if booking.status != "pending_payment":
        raise _conflict("This booking can no longer be paid. Please book again.")

    payment = await session.scalar(select(Payment).where(Payment.booking_id == booking.id, Payment.kind == "hold"))
    if payment is None:
        raise _conflict("Payment hasn't been started for this booking")

    try:
        info = await paypal.authorize_order(payment.paypal_order_id, request_id=f"authorize-{payment.paypal_order_id}")
    except PayPalError as err:
        payment.last_paypal_debug_id = err.debug_id
        await session.commit()
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "PayPal couldn't place the hold. Try another payment method.")

    now = get_clock().now()
    payment.status = "authorized"
    payment.paypal_authorization_id = info.authorization_id
    payment.method = info.payment_method
    payment.card_brand = info.card_brand
    payment.card_last_digits = info.card_last_digits
    payment.authorized_at = now
    payment.honor_period_ends_at = now + HONOR_PERIOD
    payment.expires_at = _parse_paypal_time(info.expiration_time)

    booking.status = "confirmed"
    booking.confirmation_number = new_confirmation_number()
    audit.record(session, actor_type="client", action="booking.confirmed",
                 business_id=booking.business_id, booking_id=booking.id,
                 details={"held_amount": str(payment.amount), "method": info.payment_method,
                          "paypal_authorization_id": info.authorization_id})
    await session.commit()
    await session.refresh(booking)
    return booking