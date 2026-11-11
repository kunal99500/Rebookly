"""What happens when a booking ends: cancelled, attended, or missed.

Every outcome goes through the rules engine, which produces a decision about the held money:
  * allowed outright (free cancellation, attended)  -> executed straight away (void or capture)
  * a fee                                           -> waits for the owner to approve, lower, or waive
The AI never takes part in any of this.
"""
import uuid
from datetime import datetime
from decimal import Decimal
import logging

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.documents.issue import issue_for_decision, issue_safely
from app.models import Booking, Decision, Payment, Slot
from app.notifications import booking_messages
from app.notifications.outbox import notify_safely
from app.payments.paypal import PayPalClient, PayPalError
from app.rules.engine import Action, BookingFacts, Decision as EngineDecision, Event, Policy, decide
from app.rules.outcomes import initial_status, payment_status_after_capture, settle_from_paypal
from app.services import audit, waitlist

logger = logging.getLogger("rebookly.outcomes")

CANCEL_EVENTS = (Event.CLIENT_CANCELLED, Event.OWNER_CANCELLED)
NEW_BOOKING_STATUS = {
    Event.CLIENT_CANCELLED: "cancelled",
    Event.OWNER_CANCELLED: "cancelled",
    Event.ATTENDED: "attended",
    Event.NO_SHOW: "no_show",
}


def _policy(booking: Booking) -> Policy:
    return Policy.from_dict({**booking.policy_snapshot, "version": booking.policy_version})


async def _active_hold(session: AsyncSession, booking: Booking) -> Payment:
    payment = await session.scalar(select(Payment).where(
        Payment.booking_id == booking.id, Payment.kind == "hold", Payment.status == "authorized"))
    if payment is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This booking has no active hold")
    return payment


def _facts(booking: Booking, held: Decimal, event: Event, now: datetime) -> BookingFacts:
    return BookingFacts(
        appointment_start=booking.starts_at,
        held_amount=held,
        event=event,
        event_time=now if event in CANCEL_EVENTS else None,
        slot_refilled=False,  # waitlist refills are added in a later step
    )


async def preview(session: AsyncSession, booking: Booking, event: Event) -> tuple[EngineDecision, Payment]:
    """What the engine would decide right now, without changing anything."""
    payment = await _active_hold(session, booking)
    now = get_clock().now()
    return decide(_facts(booking, payment.amount, event, now), _policy(booking), now), payment


async def apply_event(
    session: AsyncSession, paypal: PayPalClient, booking_id: uuid.UUID, event: Event,
    actor_type: str, actor_id: uuid.UUID | None,
) -> tuple[Booking, Decision]:
    """Record an outcome, create the money decision, and run it if no approval is needed."""
    now = get_clock().now()
    # Lock the booking so two outcomes (e.g. a cancel and a check-in) can't be applied at once.
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This booking is already {booking.status.replace('_', ' ')}")

    payment = await _active_hold(session, booking)
    result = decide(_facts(booking, payment.amount, event, now), _policy(booking), now)
    if result.action == Action.WAIT:
        raise HTTPException(status.HTTP_409_CONFLICT, result.reason)

    booking.status = NEW_BOOKING_STATUS[event]
    if event in CANCEL_EVENTS:
        booking.cancelled_at = now
        booking.cancelled_by = "client" if event == Event.CLIENT_CANCELLED else "owner"
        if booking.slot_id is not None:  # class bookings give their seat back
            await session.execute(update(Slot).where(Slot.id == booking.slot_id, Slot.booked_count > 0)
                                  .values(booked_count=Slot.booked_count - 1))
    elif event == Event.ATTENDED:
        booking.checked_in_at = now
    elif event == Event.NO_SHOW:
        booking.no_show_marked_at = now

    decision_id = uuid.uuid4()
    row = Decision(
        id=decision_id, booking_id=booking.id, payment_id=payment.id,
        event=event.value, action=result.action.value, amount=result.amount, rule=result.rule,
        reason=result.reason, fee_capped=result.fee_capped, needs_owner_approval=result.needs_owner_approval,
        suggested_action=result.suggested_action.value if result.suggested_action else None,
        status=initial_status(result),
        paypal_request_id=f"decision-{decision_id}",  # idempotency key: PayPal never runs it twice
    )
    session.add(row)
    audit.record(session, actor_type=actor_type, actor_id=actor_id, action=f"booking.{event.value}",
                 business_id=booking.business_id, booking_id=booking.id,
                 details={"decision_id": str(decision_id), "action": row.action, "amount": str(row.amount)})
    await session.flush()
    # Cancellation emails to both sides, and "fee waiting for approval" to the owner.
    await notify_safely(session, booking_messages.booking_outcome(session, booking, row))
    await session.commit()

    if row.status == "approved":
           row = await execute(session, paypal, row.id)
    await session.refresh(booking)
    if event in CANCEL_EVENTS:
           # Recover the booking first: offer the freed time to people on the waitlist.
           try:
               await waitlist.offer_freed_time(session, booking)
           except Exception:
               logger.exception("Couldn't offer a freed time to the waitlist")
    return booking, row


async def execute(session: AsyncSession, paypal: PayPalClient, decision_id: uuid.UUID) -> Decision:
    """Carry out an approved decision with PayPal: capture (all or part) or void the hold."""
    decision = await session.scalar(select(Decision).where(Decision.id == decision_id).with_for_update())
    if decision is None or decision.status != "approved":
        return decision
    payment = await session.get(Payment, decision.payment_id)
    decision.status = "executing"  # visible if the server stops half-way, so it can be retried safely
    await session.commit()

    amount = decision.final_amount if decision.final_amount is not None else decision.amount
    waived = decision.needs_owner_approval and amount == 0  # the owner chose not to charge a fee
    now = get_clock().now()
    try:
        if decision.action == "capture" and amount > 0:
            result = await paypal.capture_authorization(
                payment.paypal_authorization_id, amount=amount, currency=payment.currency,
                final_capture=True, request_id=decision.paypal_request_id,
            )
            payment.amount_captured = payment.amount_captured + amount
            payment.status = payment_status_after_capture(payment.amount, payment.amount_captured)
            payment.captures = [*payment.captures, {"id": result.get("id"), "amount": str(amount), "at": now.isoformat()}]
            money_action = "payment.captured"
        else:
            await paypal.void_authorization(payment.paypal_authorization_id, request_id=decision.paypal_request_id)
            payment.status = "voided"
            money_action = "payment.voided"
        decision.status = "waived" if waived else "executed"
        decision.final_amount = amount if decision.action == "capture" else Decimal("0")
        decision.executed_at = now
    except PayPalError as err:
        decision.status = "failed"
        decision.failure_reason = err.message[:500]
        decision.last_paypal_debug_id = payment.last_paypal_debug_id = err.debug_id
        money_action = "payment.failed"

    booking = await session.get(Booking, decision.booking_id)
    audit.record(session, actor_type="system", action=money_action, business_id=booking.business_id,
                 booking_id=booking.id, details={"decision_id": str(decision.id), "amount": str(amount),
                                                 "paypal_debug_id": decision.last_paypal_debug_id})
    await issue_safely(session, issue_for_decision(session, decision))           # receipt or release notice
    await notify_safely(session, booking_messages.money_settled(session, decision))  # email about the money
    await session.commit()
    await session.refresh(decision)
    return decision


async def _pending(session: AsyncSession, decision_id: uuid.UUID) -> Decision:
    decision = await session.scalar(select(Decision).where(Decision.id == decision_id).with_for_update())
    if decision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decision not found")
    if decision.status != "pending_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, "This decision has already been handled")
    return decision


async def approve(
    session: AsyncSession, paypal: PayPalClient, decision_id: uuid.UUID, owner_id: uuid.UUID,
    final_amount: Decimal | None, note: str | None,
) -> Decision:
    decision = await _pending(session, decision_id)
    if decision.action != "capture":
        raise HTTPException(status.HTTP_409_CONFLICT, "There is no fee to approve here. Waive it instead.")
    amount = decision.amount if final_amount is None else final_amount
    if amount > decision.amount:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"You can charge at most {decision.amount} under the agreed policy")
    decision.final_amount = amount
    decision.approved_by_user_id, decision.approved_at = owner_id, get_clock().now()
    decision.owner_note, decision.status = note, "approved"
    booking = await session.get(Booking, decision.booking_id)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="decision.approved",
                 business_id=booking.business_id, booking_id=booking.id,
                 details={"decision_id": str(decision.id), "final_amount": str(amount)})
    await session.commit()
    return await execute(session, paypal, decision.id)


async def waive(
    session: AsyncSession, paypal: PayPalClient, decision_id: uuid.UUID, owner_id: uuid.UUID, note: str | None,
) -> Decision:
    decision = await _pending(session, decision_id)
    decision.final_amount = Decimal("0")
    decision.action = "capture" if decision.action == "capture" else "void"
    decision.approved_by_user_id, decision.approved_at = owner_id, get_clock().now()
    decision.owner_note, decision.status = note, "approved"
    booking = await session.get(Booking, decision.booking_id)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="decision.waived",
                 business_id=booking.business_id, booking_id=booking.id, details={"decision_id": str(decision.id)})
    await session.commit()
    return await execute(session, paypal, decision.id)


async def recover(session: AsyncSession, paypal: PayPalClient, decision_id: uuid.UUID) -> Decision:
    """Finish a decision that got stuck ("executing") or failed, without ever charging twice.

    We first ask PayPal what actually happened to the hold:
      * PayPal already did it  -> just record it,
      * the hold is untouched  -> try again with a fresh request ID,
      * the hold can't be used -> mark failed with a clear reason.
    """
    decision = await session.scalar(select(Decision).where(Decision.id == decision_id).with_for_update())
    if decision is None or decision.status not in ("executing", "failed"):
        return decision
    payment = await session.get(Payment, decision.payment_id)
    booking = await session.get(Booking, decision.booking_id)
    amount = decision.final_amount if decision.final_amount is not None else decision.amount
    intended = "capture" if decision.action == "capture" and amount > 0 else "void"

    try:
        authorization = await paypal.get_authorization(payment.paypal_authorization_id)
    except PayPalError:
        return decision  # PayPal unreachable; the next run will try again

    paypal_status = authorization.get("status", "")
    verdict = settle_from_paypal(intended, paypal_status)
    now = get_clock().now()

    if verdict == "retry":
        decision.status = "approved"
        # A new request ID is safe here: PayPal has just confirmed the hold is untouched.
        decision.paypal_request_id = f"decision-{decision.id}-retry-{int(now.timestamp())}"
        await session.commit()
        return await execute(session, paypal, decision.id)

    if verdict == "already_done":
        if intended == "capture":
            payment.amount_captured = payment.amount_captured + amount
            payment.status = payment_status_after_capture(payment.amount, payment.amount_captured)
            payment.captures = [*payment.captures,
                                {"id": None, "amount": str(amount), "at": now.isoformat(), "reconciled": True}]
        else:
            payment.status = "voided"
        decision.status = "waived" if decision.needs_owner_approval and amount == 0 else "executed"
        decision.final_amount = amount if intended == "capture" else Decimal("0")
        decision.executed_at, decision.failure_reason = now, None
        action = "payment.reconciled"
    else:
        decision.status = "failed"
        decision.failure_reason = f"PayPal shows this hold as {paypal_status or 'unknown'}, so it can't be completed"
        action = "payment.unrecoverable"

    audit.record(session, actor_type="system", action=action, business_id=booking.business_id, booking_id=booking.id,
                 details={"decision_id": str(decision.id), "paypal_status": paypal_status})
    await issue_safely(session, issue_for_decision(session, decision))
    await notify_safely(session, booking_messages.money_settled(session, decision))
    await session.commit()
    await session.refresh(decision)
    return decision