"""The client assistant's tools, backed by the database. Every lookup is limited to the signed-in client's
own bookings (found by confirmation number AND client), and nothing here changes a booking or moves money."""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.assistant import ClientTools, ProposedAction, ToolError
from app.clock import get_clock
from app.models import AvailabilityRule, Booking, Business, Client
from app.rules.engine import Action, Event
from app.rules.formatting import local_time, money
from app.rules.policy_text import policy_summary
from app.services import bookings, offerings, outcomes, policies, rescheduling

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class DbClientTools(ClientTools):
    def __init__(self, session: AsyncSession, client: Client):
        super().__init__()
        self.session, self.client = session, client

    async def _booking(self, ref: str) -> tuple[Booking, Business]:
        booking = await self.session.scalar(select(Booking).where(
            Booking.confirmation_number == ref.strip().upper(), Booking.client_id == self.client.id))
        if booking is None:
            raise ToolError("I couldn't find that booking among this client's bookings")
        return booking, await self.session.get(Business, booking.business_id)

    async def _visit(self, booking: Booking) -> str:
        return (await bookings.visit_summaries(self.session, [booking.id])).get(booking.id, "booking")

    async def list_my_bookings(self) -> dict:
        now = get_clock().now()
        rows = list(await self.session.scalars(select(Booking).where(
            Booking.client_id == self.client.id, Booking.confirmation_number.is_not(None),
            Booking.starts_at > now - timedelta(days=30)).order_by(Booking.starts_at).limit(20)))
        visits = await bookings.visit_summaries(self.session, [b.id for b in rows])
        result = []
        for b in rows:
            business = await self.session.get(Business, b.business_id)
            free_hours = int((b.policy_snapshot or {}).get("free_cancel_hours", 0))
            item = {"ref": b.confirmation_number, "business": business.name, "business_slug": business.slug,
                    "visit": visits.get(b.id, "booking"), "when": local_time(b.starts_at, business.timezone),
                    "status": b.status, "deposit_held": money(b.held_amount, b.currency),
                    "upcoming": b.starts_at > now}
            if b.status == "confirmed" and b.starts_at > now and free_hours:
                item["free_cancellation_until"] = local_time(b.starts_at - timedelta(hours=free_hours), business.timezone)
            result.append(item)
        return {"bookings": result}

    async def cancellation_preview(self, ref: str) -> dict:
        booking, business = await self._booking(ref)
        if booking.status != "confirmed":
            raise ToolError(f"This booking is {booking.status.replace('_', ' ')}, so it can't be cancelled")
        decision, payment = await outcomes.preview(self.session, booking, Event.CLIENT_CANCELLED)
        fee = decision.amount if decision.action == Action.CAPTURE else 0
        return {"fee_up_to": money(fee, booking.currency), "released": money(payment.amount - fee, booking.currency),
                "reason": decision.reason, "business_reviews_fee": decision.needs_owner_approval}

    async def reschedule_options(self, ref: str, day: date | None) -> dict:
        booking, business = await self._booking(ref)
        times = await rescheduling.options(self.session, booking, day)
        return {"times": [{"starts_at": t.starts_at.isoformat(), "label": local_time(t.starts_at, business.timezone)}
                          for t in times[:12]],
                "note": "Only these times are possible." if times else "No other times are possible right now."}

    async def propose_reschedule(self, ref: str, starts_at: datetime) -> dict:
        booking, business = await self._booking(ref)
        times = await rescheduling.options(self.session, booking)
        if not any(t.starts_at == starts_at for t in times):
            raise ToolError("That time isn't available for this booking. Use one from reschedule_options.")
        visit = await self._visit(booking)
        label = local_time(starts_at, business.timezone)
        self.actions.append(ProposedAction(
            type="reschedule", booking_id=booking.id, starts_at=starts_at,
            title=f"Move {visit} at {business.name} to {label}",
            details="Same services, same deposit and the same cancellation policy."))
        return {"prepared": True, "tell_the_client": "Ask them to tap Confirm on the card to move it."}

    async def propose_cancel(self, ref: str) -> dict:
        preview = await self.cancellation_preview(ref)
        booking, business = await self._booking(ref)
        visit = await self._visit(booking)
        if preview["fee_up_to"] == money(0, booking.currency):
            details = f"No fee: {preview['released']} is released."
        else:
            details = (f"Up to {preview['fee_up_to']} may be kept under the policy you agreed to"
                       f"{' (the business reviews it first)' if preview['business_reviews_fee'] else ''}; "
                       f"the rest is released.")
        self.actions.append(ProposedAction(
            type="cancel", booking_id=booking.id,
            title=f"Cancel {visit} at {business.name}, {local_time(booking.starts_at, business.timezone)}",
            details=details))
        return {"prepared": True, "cost": details, "tell_the_client": "Ask them to tap Confirm on the card to cancel."}

    async def business_info(self, slug: str) -> dict:
        business = await self.session.scalar(select(Business).where(Business.slug == slug, Business.status == "live"))
        if business is None:
            raise ToolError("No live business with that slug")
        services = await offerings.list_services(self.session, business, include_inactive=False)
        stored = await policies.get_policy(self.session, business, business.current_policy_version)
        hours = list(await self.session.scalars(select(AvailabilityRule).where(
            AvailabilityRule.business_id == business.id).order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)))
        return {
            "name": business.name, "description": business.description,
            "services": [{"name": s.name, "type": "extra (add-on)" if s.kind == "add_on" else "service",
                          "minutes": s.duration_minutes, "price": money(s.price, business.currency),
                          "deposit": money(s.deposit, business.currency)} for s in services],
            "opening_hours": [f"{DAYS[h.weekday]} {h.start_time:%H:%M}-{h.end_time:%H:%M}" for h in hours],
            "policy": policy_summary(policies.to_engine_policy(stored.rules, stored.version)),
        }