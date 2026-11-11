"""Handling PayPal webhook events.

1. Record the event (its PayPal ID is unique, so a repeated delivery is recognised and skipped).
2. Find our payment from the IDs in the event.
3. Ask PayPal for the current state (never trust the event body for money) and bring our records in line.

What each event can lead to:
  * order approved, but the client's page never finished -> complete the booking (place the hold)
  * hold voided or expired on PayPal's side               -> record it, alert the owner
  * our record and PayPal disagree on a finished payment  -> record the conflict, alert the owner
  * a dispute                                              -> alert the owner
"""
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.models import Booking, Decision, Payment, PayPalWebhookEvent
from app.notifications import booking_messages
from app.notifications.outbox import notify_safely
from app.payments.paypal import PayPalClient, PayPalError
from app.rules.paypal_sync import category, references, sync
from app.services import audit

logger = logging.getLogger("rebookly.webhooks")
MAX_ATTEMPTS = 5


async def record(session: AsyncSession, event: dict) -> PayPalWebhookEvent | None:
    """Save the event. Returns None if we've already received it."""
    event_id = str(event.get("id") or "")[:64]
    if not event_id:
        return None
    inserted = await session.scalar(
        insert(PayPalWebhookEvent).values(
            paypal_event_id=event_id, event_type=str(event.get("event_type", ""))[:80],
            refs=references(event), status="received",
        ).on_conflict_do_nothing(index_elements=["paypal_event_id"]).returning(PayPalWebhookEvent.id))
    await session.commit()
    return await session.get(PayPalWebhookEvent, inserted) if inserted else None


async def process(session: AsyncSession, paypal: PayPalClient, row: PayPalWebhookEvent) -> str:
    """Handle one recorded event. Safe to run again: everything it does checks the current state first."""
    row.attempts += 1
    try:
        kind = category(row.event_type)
        if kind == "order_approved":
            outcome = await _order_approved(session, paypal, row.refs.get("order_id"))
        elif kind in ("authorization", "capture"):
            outcome = await _sync_authorization(session, paypal, row.refs.get("authorization_id"))
        elif kind == "dispute":
            outcome = await _dispute(session, row.refs)
        else:
            outcome = "ignored"
        row.status, row.error, row.processed_at = outcome, None, get_clock().now()
    except PayPalError as err:   # PayPal unreachable: try again later
        row.status, row.error = ("failed", f"PayPal: {err.message}"[:300])
    except Exception as err:
        logger.exception("Webhook %s failed", row.paypal_event_id)
        row.status, row.error = "failed", f"{type(err).__name__}: {err}"[:300]
    await session.commit()
    return row.status


async def _payment_by(session: AsyncSession, **where) -> Payment | None:
    (column, value), = where.items()
    if not value:
        return None
    return await session.scalar(select(Payment).where(getattr(Payment, column) == value, Payment.kind == "hold"))


async def _order_approved(session: AsyncSession, paypal: PayPalClient, order_id: str | None) -> str:
    """The client approved on PayPal. If our checkout page never finished (closed tab, lost connection),
    complete the booking now, but only while its payment window is still open."""
    from app.services import bookings   # imported here to avoid a circular import

    payment = await _payment_by(session, paypal_order_id=order_id)
    if payment is None or payment.status != "created":
        return "ignored"            # not ours, or already handled by the checkout page
    booking = await session.get(Booking, payment.booking_id)
    if booking.status != "pending_payment" or get_clock().now() >= booking.payment_expires_at:
        return "ignored"            # expired: the time may already be someone else's
    await bookings.authorize_hold(session, paypal, booking)
    audit.record(session, actor_type="system", action="booking.confirmed_by_webhook",
                 business_id=booking.business_id, booking_id=booking.id, details={"order_id": order_id})
    await session.commit()
    return "processed"


async def _sync_authorization(session: AsyncSession, paypal: PayPalClient, authorization_id: str | None) -> str:
    payment = await _payment_by(session, paypal_authorization_id=authorization_id)
    if payment is None:
        return "ignored"
    in_flight = await session.scalar(select(Decision.id).where(
        Decision.payment_id == payment.id, Decision.status.in_(("approved", "executing"))))
    if in_flight is not None:
        return "processed"          # our own capture or void is running; the recovery job reconciles it
    paypal_status = (await paypal.get_authorization(authorization_id)).get("status", "")
    result = sync(payment.status, paypal_status)
    if result.kind == "none":
        return "processed"

    booking = await session.get(Booking, payment.booking_id)
    details = {"ours": payment.status, "paypal": paypal_status}
    if result.kind == "update":
        payment.status = result.new_status
        audit.record(session, actor_type="system", action="payment.synced_from_paypal",
                     business_id=booking.business_id, booking_id=booking.id, details=details)
        if result.new_status in ("voided", "expired") and booking.status == "confirmed" \
                and booking.starts_at > get_clock().now():
            await notify_safely(session, booking_messages.payment_alert(
                session, booking, "hold_lost", f"{authorization_id}:{result.new_status}",
                paypal_status=paypal_status.lower()))
    else:
        audit.record(session, actor_type="system", action="payment.mismatch",
                     business_id=booking.business_id, booking_id=booking.id, details=details)
        await notify_safely(session, booking_messages.payment_alert(
            session, booking, "payment_failed", f"mismatch:{authorization_id}:{paypal_status}",
            error=f"Our records say {payment.status}, PayPal says {paypal_status.lower()}. Please check PayPal."))
    await session.commit()
    return "processed"


async def _dispute(session: AsyncSession, refs: dict) -> str:
    for capture_id in refs.get("capture_ids", []):
        payment = await session.scalar(select(Payment).where(Payment.captures.contains([{"id": capture_id}])))
        if payment is None:
            continue
        booking = await session.get(Booking, payment.booking_id)
        audit.record(session, actor_type="system", action="payment.dispute_opened",
                     business_id=booking.business_id, booking_id=booking.id,
                     details={"dispute_id": refs.get("dispute_id"), "capture_id": capture_id})
        await notify_safely(session, booking_messages.payment_alert(
            session, booking, "payment_dispute", f"dispute:{refs.get('dispute_id')}"))
        await session.commit()
        return "processed"
    return "ignored"


async def retry_failed(session_factory, paypal: PayPalClient) -> int:
    """Background job: try failed events again (at most MAX_ATTEMPTS times each)."""
    since = get_clock().now() - timedelta(days=3)
    async with session_factory() as session:
        ids = list(await session.scalars(select(PayPalWebhookEvent.id).where(
            PayPalWebhookEvent.status == "failed", PayPalWebhookEvent.attempts < MAX_ATTEMPTS,
            PayPalWebhookEvent.received_at > since).limit(50)))
    done = 0
    for event_id in ids:
        async with session_factory() as session:
            row = await session.scalar(select(PayPalWebhookEvent).where(
                PayPalWebhookEvent.id == event_id).with_for_update(skip_locked=True))
            if row is not None and row.status == "failed":
                done += (await process(session, paypal, row)) != "failed"
    return done