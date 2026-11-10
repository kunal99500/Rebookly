"""What the owner should look at right now. Calculated on request, so it's always current."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Business, Client, Decision, Payment, Service
from app.rules.outcomes import is_possible_no_show
from app.schemas.dashboard import AttentionBooking, AttentionOut

HOLD_WARNING = timedelta(hours=12)


async def needs_attention(session: AsyncSession, business: Business, now: datetime) -> AttentionOut:
    started = await session.execute(
        select(Booking, Client.name, Service.name)
        .join(Client, Client.id == Booking.client_id).join(Service, Service.id == Booking.service_id)
        .where(Booking.business_id == business.id, Booking.status == "confirmed",
               Booking.starts_at <= now, Booking.starts_at > now - timedelta(days=1))
        .order_by(Booking.starts_at)
    )
    no_shows = [
        _item(b, client, service) for b, client, service in started
        if is_possible_no_show(b.starts_at, int(b.policy_snapshot.get("grace_minutes", 0)),
                               b.checked_in_at is not None, now)
    ]

    counts = dict((await session.execute(
        select(Decision.status, func.count()).join(Booking, Booking.id == Decision.booking_id)
        .where(Booking.business_id == business.id, Decision.status.in_(("pending_approval", "failed")))
        .group_by(Decision.status)
    )).all())

    ending = await session.execute(
        select(Booking, Client.name, Service.name)
        .join(Client, Client.id == Booking.client_id).join(Service, Service.id == Booking.service_id)
        .join(Payment, (Payment.booking_id == Booking.id) & (Payment.kind == "hold"))
        .where(Booking.business_id == business.id, Booking.status == "confirmed",
               Payment.status == "authorized", Payment.honor_period_ends_at < now + HOLD_WARNING)
    )
    return AttentionOut(
        possible_no_shows=no_shows,
        pending_approvals=counts.get("pending_approval", 0),
        failed_payments=counts.get("failed", 0),
        holds_ending_soon=[_item(b, client, service) for b, client, service in ending],
    )


def _item(booking: Booking, client_name: str, service_name: str) -> AttentionBooking:
    return AttentionBooking(booking_id=booking.id, client_name=client_name, service_name=service_name,
                            starts_at=booking.starts_at, held_amount=booking.held_amount, currency=booking.currency)