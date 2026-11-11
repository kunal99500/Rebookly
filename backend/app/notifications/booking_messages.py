"""Which messages each booking event produces, and the facts they're written from."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Booking, BookingItem, Business, Client, Decision
from app.notifications.outbox import enqueue
from app.rules.formatting import local_time, money


async def _facts(session: AsyncSession, booking: Booking) -> tuple[Business, Client, dict]:
    business = await session.get(Business, booking.business_id)
    client = await session.get(Client, booking.client_id)
    names = list(await session.scalars(select(BookingItem.name).where(BookingItem.booking_id == booking.id)
                                       .order_by(BookingItem.position)))
    free_hours = int((booking.policy_snapshot or {}).get("free_cancel_hours", 0))
    payload = {
        "business_name": business.name,
        "visit": " + ".join(names) or "your booking",
        "when": local_time(booking.starts_at, business.timezone),
        "held": money(booking.held_amount, booking.currency),
        "ref": booking.confirmation_number or "",
        "client_name": client.name,
        "policy_line": f"Free cancellation up to {free_hours} hours before." if free_hours else "",
    }
    return business, client, payload


def _client_email(client: Client) -> str | None:
    return client.email if client.email and client.email_verified_at else None


def _links() -> tuple[str, str]:
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/my", f"{base}/business"


async def _send(session, booking, kind, to, who, payload, link, suffix=""):
    if to:
        await enqueue(session, kind=kind, to_address=to, recipient_type=who, business_id=booking.business_id,
                      booking_id=booking.id, payload={**payload, "link": link},
                      dedupe_key=f"{kind}:{booking.id}:{who}{suffix}")


async def booking_confirmed(session: AsyncSession, booking: Booking) -> None:
    business, client, facts = await _facts(session, booking)
    client_link, owner_link = _links()
    await _send(session, booking, "booking_confirmed", _client_email(client), "client", facts, client_link)
    await _send(session, booking, "new_booking", business.notification_email, "owner", facts, owner_link)


async def booking_rescheduled(session: AsyncSession, booking: Booking) -> None:
    business, client, facts = await _facts(session, booking)
    client_link, _ = _links()
    await _send(session, booking, "booking_rescheduled", _client_email(client), "client", facts, client_link,
                suffix=f":{booking.starts_at.isoformat()}")


async def booking_outcome(session: AsyncSession, booking: Booking, decision: Decision) -> None:
    """Cancellations to both sides; fees waiting for approval to the owner."""
    business, client, facts = await _facts(session, booking)
    client_link, owner_link = _links()
    if booking.status == "cancelled":
        by = "by you" if booking.cancelled_by == "client" else f"by {business.name}"
        await _send(session, booking, "booking_cancelled", _client_email(client), "client",
                    {**facts, "by": by, "outcome": ""}, client_link)
        if booking.cancelled_by == "client":
            await _send(session, booking, "booking_cancelled", business.notification_email, "owner",
                        {**facts, "by": f"by {client.name}", "outcome": ""}, owner_link)
    if decision.status == "pending_approval":
        await _send(session, booking, "fee_pending", business.notification_email, "owner",
                    {**facts, "amount": money(decision.amount, booking.currency), "reason": decision.reason},
                    owner_link, suffix=f":{decision.id}")


async def money_settled(session: AsyncSession, decision: Decision) -> None:
    """After PayPal: fee charged or hold released (to the client), or a failure (to the owner)."""
    booking = await session.get(Booking, decision.booking_id)
    business, client, facts = await _facts(session, booking)
    client_link, owner_link = _links()
    held = booking.held_amount
    charged = decision.final_amount if decision.final_amount is not None else decision.amount
    if decision.status == "failed":
        await _send(session, booking, "payment_failed", business.notification_email, "owner",
                    {**facts, "error": decision.failure_reason or "unknown error"}, owner_link,
                    suffix=f":{decision.id}")
        return
    if decision.status not in ("executed", "waived") or decision.event == "attended":
        return  # attended: the payment receipt is enough
    if decision.action == "capture" and charged and charged > 0:
        await _send(session, booking, "fee_charged", _client_email(client), "client",
                    {**facts, "amount": money(charged, booking.currency),
                     "released": money(held - charged, booking.currency), "reason": decision.reason},
                    client_link, suffix=f":{decision.id}")
    else:
        await _send(session, booking, "hold_released", _client_email(client), "client",
                    {**facts, "released": money(held, booking.currency)}, client_link, suffix=f":{decision.id}")


async def reminder(session: AsyncSession, booking: Booking, kind: str) -> None:
    business, client, facts = await _facts(session, booking)
    client_link, _ = _links()
    await _send(session, booking, kind, _client_email(client), "client", facts, client_link)


async def payment_alert(session: AsyncSession, booking: Booking, kind: str, key: str, **extra) -> None:
    """Owner alerts from PayPal events: a hold lost on PayPal's side, or a dispute."""
    business, client, facts = await _facts(session, booking)
    _, owner_link = _links()
    await _send(session, booking, kind, business.notification_email, "owner", {**facts, **extra}, owner_link,
                suffix=f":{key}")