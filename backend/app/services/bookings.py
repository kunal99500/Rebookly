"""Creating bookings and placing their PayPal holds.

Order of work when a client books:
  1. Lock the business briefly, check the time is still free, save a pending booking.  (one transaction)
  2. Create the PayPal order for the hold.                                              (outside the lock)
  3. The client approves on the checkout page; we authorize, and the booking is confirmed.
If anything fails after step 1, the booking is released.

A booking can contain several services (e.g. haircut + wash) performed by one staff member.
The database refuses overlapping appointments for the same staff member, so even two clients
confirming at the same instant can never be double-booked.
"""
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.documents.issue import issue_confirmation, issue_safely
from app.models import (
    Booking, BookingItem, Business, BusinessPolicy, Client, Payment, Service, Slot, Staff,
)
from app.payments.paypal import PayPalClient, PayPalError
from app.rules.booking import (
    MAX_ACTIVE_BOOKINGS_PER_BUSINESS, PAYMENT_WINDOW_MINUTES, new_check_in_token, new_confirmation_number,
)
from app.rules.pricing import VisitError, strictest_policy
from app.schemas.client import BookingCreate
from app.services import audit, availability

HONOR_PERIOD = timedelta(days=3)
ACTIVE = ("pending_payment", "confirmed")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


async def create_booking(session: AsyncSession, client: Client, data: BookingCreate) -> Booking:
    """Step 1: check the time is still free for the whole visit, and save a pending booking. No PayPal yet."""
    now = get_clock().now()
    first = await session.get(Service, data.service_ids[0])
    if first is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That service isn't available")
    business = await session.get(Business, first.business_id)

    # Lock this business's row until we commit, so two bookings can't pass the checks below at once.
    await session.execute(select(Business.id).where(Business.id == business.id).with_for_update())
    if business.status != "live" or business.current_policy_version is None:
        raise _conflict("This business isn't taking bookings right now")

    # Re-check availability now, with the same rules the client saw (services, staff, hours, notice).
    plan, staff, options = await availability.available_times(
        session, business, data.service_ids, data.staff_id, now)
    match = next((o for o in options if o.starts_at == data.starts_at), None)
    if match is None:
        raise _conflict("Sorry, that time is no longer available. Please pick another.")
    chosen = next(s for s in staff if s.id == match.staff_ids[0])  # first free person, in the owner's order
    try:
        held = plan.hold_for(data.payment_option)
    except VisitError as err:
        raise _conflict(str(err))

    active = await session.scalar(select(func.count()).select_from(Booking).where(
        Booking.client_id == client.id, Booking.business_id == business.id,
        Booking.status.in_(ACTIVE), Booking.starts_at > now,
    ))
    if active >= MAX_ACTIVE_BOOKINGS_PER_BUSINESS:
        raise _conflict(f"You can have up to {MAX_ACTIVE_BOOKINGS_PER_BUSINESS} upcoming bookings here")

    # The exact policy this client agrees to: the business's, or a stricter one from a chosen service.
    policy = await session.scalar(select(BusinessPolicy).where(
        BusinessPolicy.business_id == business.id, BusinessPolicy.version == business.current_policy_version))
    overrides = list(await session.scalars(select(Service.policy_override).where(Service.id.in_(data.service_ids))))

    booking = Booking(
        id=uuid.uuid4(),
        business_id=business.id, service_id=plan.lines[0].service_id, slot_id=None,
        location_id=chosen.location_id, staff_id=chosen.id, client_id=client.id,
        attendee_name=data.attendee_name,
        status="pending_payment",
        payment_option=data.payment_option,
        price=plan.price,
        held_amount=held,
        currency=business.currency,
        policy_version=policy.version,
        policy_snapshot=strictest_policy(policy.rules, overrides),
        starts_at=match.starts_at,
        ends_at=match.ends_at,
        occupied_until=match.starts_at + timedelta(minutes=plan.occupied_minutes),
        payment_expires_at=now + timedelta(minutes=PAYMENT_WINDOW_MINUTES),
        check_in_token=new_check_in_token(),
    )
    session.add(booking)
    for position, line in enumerate(plan.lines, start=1):
        session.add(BookingItem(
            booking_id=booking.id, service_id=line.service_id, position=position, kind=line.kind,
            name=line.name, duration_minutes=line.duration_minutes, price=line.price, deposit=line.deposit,
        ))
    audit.record(session, actor_type="client", actor_id=client.auth_user_id, action="booking.started",
                 business_id=business.id, booking_id=booking.id,
                 details={"staff_id": str(chosen.id), "services": len(plan.lines), "held_amount": str(held)})
    try:
        await session.commit()
    except IntegrityError:
        # The database's overlap protection caught a booking made at the very same moment.
        await session.rollback()
        raise _conflict("Sorry, that time was just taken. Please pick another.")
    await session.refresh(booking)
    return booking


async def visit_summaries(session: AsyncSession, booking_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """"Haircut + Hair wash" for each booking, in the order the services happen."""
    rows = await session.execute(
        select(BookingItem.booking_id, BookingItem.name).where(BookingItem.booking_id.in_(booking_ids))
        .order_by(BookingItem.booking_id, BookingItem.position)
    )
    names: dict[uuid.UUID, list[str]] = {}
    for booking_id, name in rows:
        names.setdefault(booking_id, []).append(name)
    return {booking_id: " + ".join(parts) for booking_id, parts in names.items()}


async def release_seat(session: AsyncSession, booking: Booking, reason: str) -> None:
    """Release a booking that never got paid (its time becomes free again)."""
    if booking.status != "pending_payment":
        return
    booking.status = "expired"
    if booking.slot_id is not None:  # class bookings also give their seat back
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
    summary = (await visit_summaries(session, [booking.id])).get(booking.id, "Booking")
    try:
        order = await paypal.create_order(
            amount=booking.held_amount,
            currency=booking.currency,
            reference_id=str(booking.id),
            description=f"{business.name}: {summary} (deposit hold)",
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
    await issue_safely(session, issue_confirmation(session, booking))
    await session.commit()
    await session.refresh(booking)
    return booking


async def staff_name(session: AsyncSession, booking: Booking) -> str | None:
    if booking.staff_id is None:
        return None
    return await session.scalar(select(Staff.name).where(Staff.id == booking.staff_id))