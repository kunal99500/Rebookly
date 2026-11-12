"""Deleting a client's personal data (their right to be forgotten), while keeping the financial records
businesses must keep by law, no longer linked to any contact details."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.models import Booking, Client, Decision, Notification, Review, WaitlistEntry
from app.rules.account_deletion import DELETED_NAME, deletion_blockers
from app.services import audit
from app.services.reviews import _refresh_rating


async def blockers(session: AsyncSession, client: Client) -> list[str]:
    now = get_clock().now()
    upcoming = await session.scalar(select(func.count()).select_from(Booking).where(
        Booking.client_id == client.id, Booking.status == "confirmed", Booking.starts_at > now))
    unpaid = await session.scalar(select(func.count()).select_from(Booking).where(
        Booking.client_id == client.id, Booking.status == "pending_payment"))
    fees = await session.scalar(select(func.count()).select_from(Decision).join(Booking).where(
        Booking.client_id == client.id, Decision.status.in_(("pending_approval", "approved", "executing"))))
    return deletion_blockers(upcoming_bookings=upcoming, unpaid_bookings=unpaid, fees_waiting=fees)


async def delete_client_data(session: AsyncSession, client: Client) -> uuid.UUID | None:
    """Remove the client's personal data in one transaction. Returns the sign-in account ID to remove next."""
    problems = await blockers(session, client)
    if problems:
        raise HTTPException(status.HTTP_409_CONFLICT, " ".join(problems))

    # Reviews are the client's own words: delete them, and correct each business's rating.
    reviewed = list(await session.scalars(select(Review.business_id).where(Review.client_id == client.id)))
    await session.execute(delete(Review).where(Review.client_id == client.id))
    for business_id in set(reviewed):
        await _refresh_rating(session, business_id)

    await session.execute(delete(WaitlistEntry).where(WaitlistEntry.client_id == client.id))
    # Messages to the client: unsent ones are dropped; sent ones keep their record but lose address and content.
    addresses = [a for a in (client.email, client.email_pending) if a] or [""]
    to_client = and_(Notification.recipient_type == "client", or_(
        Notification.to_address.in_(addresses),
        Notification.booking_id.in_(select(Booking.id).where(Booking.client_id == client.id))))
    await session.execute(delete(Notification).where(to_client, Notification.status == "pending"))
    await session.execute(update(Notification).where(to_client).values(to_address="deleted", payload={}))
    await session.execute(update(Booking).where(Booking.client_id == client.id).values(attendee_name=None))

    auth_user_id = client.auth_user_id
    client.name = DELETED_NAME
    client.phone_hash = client.phone_encrypted = client.phone_last4 = client.phone_verified_at = None
    client.email = client.email_verified_at = client.email_pending = None
    client.email_code_hash = client.email_code_expires_at = None
    client.auth_user_id = None
    client.deleted_at = get_clock().now()
    audit.record(session, actor_type="client", actor_id=auth_user_id, action="client.data_deleted",
                 details={"reviews_deleted": len(reviewed)})
    await session.commit()
    return auth_user_id