"""When a late-cancelled time is booked again, the cancellation fee is dropped (if the policy says so).

Late cancellation fees wait for the owner's approval. This job checks those waiting fees: if a new booking
has taken the freed time since, the rules engine decides again with "slot refilled", and if the policy
waives the fee in that case, the waiting fee is replaced by a release of the hold.
"""
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Decision, Payment
from app.rules.engine import Action, BookingFacts, Event, Policy, decide
from app.rules.waitlist import is_refill
from app.services import audit


async def find_refill(session: AsyncSession, cancelled: Booking) -> Booking | None:
       """A booking whose deposit hold was placed after the cancellation, on the freed time (same person or class).

       "After" is judged by the hold's authorization time, which uses the app's clock like the cancellation does.
       """
       same_place = (Booking.slot_id == cancelled.slot_id) if cancelled.slot_id else and_(
           Booking.staff_id == cancelled.staff_id, Booking.starts_at < cancelled.occupied_until,
           Booking.occupied_until > cancelled.starts_at)
       candidates = await session.execute(select(Booking, Payment.authorized_at).join(
           Payment, and_(Payment.booking_id == Booking.id, Payment.kind == "hold")).where(
           Booking.business_id == cancelled.business_id, Booking.id != cancelled.id,
           Booking.status.in_(("confirmed", "attended")), Payment.authorized_at > cancelled.cancelled_at, same_place))
       for new, held_at in candidates:
           if is_refill(cancelled_at=cancelled.cancelled_at, freed_start=cancelled.starts_at,
                        freed_end=cancelled.occupied_until, freed_staff_id=cancelled.staff_id,
                        freed_slot_id=cancelled.slot_id, new_start=new.starts_at, new_end=new.occupied_until,
                        new_staff_id=new.staff_id, new_slot_id=new.slot_id, new_created_at=held_at):
               return new
       return None


async def waive_if_refilled(session: AsyncSession, decision_id: uuid.UUID) -> uuid.UUID | None:
    """If this waiting fee should be dropped because the time was rebooked, replace it with a release.

    Returns the new (approved) release decision's ID, for the caller to carry out with PayPal; otherwise None.
    """
    decision = await session.scalar(select(Decision).where(Decision.id == decision_id).with_for_update())
    if decision is None or decision.status != "pending_approval" or decision.event != "client_cancelled":
        return None
    booking = await session.get(Booking, decision.booking_id)
    refill = await find_refill(session, booking)
    if refill is None:
        return None
    policy = Policy.from_dict({**booking.policy_snapshot, "version": booking.policy_version})
    payment = await session.get(Payment, decision.payment_id)
    facts = BookingFacts(appointment_start=booking.starts_at, held_amount=payment.amount, event=Event.CLIENT_CANCELLED,
                         event_time=booking.cancelled_at, slot_refilled=True)
    result = decide(facts, policy, booking.cancelled_at)     # same moment as the cancellation, now with the refill
    if result.action != Action.VOID:
        return None                                          # this policy keeps the fee even when refilled

    decision.status = "superseded"
    new_id = uuid.uuid4()
    session.add(Decision(
        id=new_id, booking_id=booking.id, payment_id=decision.payment_id, event=decision.event,
        action="void", amount=result.amount, rule=result.rule, reason=result.reason, fee_capped=False,
        needs_owner_approval=False, suggested_action=None, status="approved",
        paypal_request_id=f"decision-{new_id}",
    ))
    audit.record(session, actor_type="system", action="decision.waived_refilled", business_id=booking.business_id,
                 booking_id=booking.id, details={"superseded": str(decision.id), "new_decision": str(new_id),
                                                 "refilled_by": str(refill.id)})
    await session.commit()
    return new_id


async def pending_late_cancellations(session: AsyncSession, limit: int = 50) -> list[uuid.UUID]:
    return list(await session.scalars(select(Decision.id).where(
        Decision.status == "pending_approval", Decision.event == "client_cancelled").limit(limit)))