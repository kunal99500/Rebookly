"""Joining the waitlist, offering freed times, and turning an offer into a booking.

The offer isn't a reservation: a few waiting clients are told at once and the first to book gets it,
through the normal booking flow (same availability check, same deposit, same policy).
"""
import uuid
from datetime import time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.config import get_settings
from app.models import Booking, Business, Client, Service, Slot, WaitlistEntry
from app.notifications.outbox import enqueue
from app.rules.catalog import BOOKING_WINDOW_HOURS
from app.rules.formatting import local_time
from app.rules.waitlist import MAX_ACTIVE_ENTRIES_PER_CLIENT, OFFERS_PER_OPENING, first_fit, offer_expiry, window
from app.schemas.waitlist import WaitlistJoin, WaitlistOut
from app.services import audit, availability

ACTIVE = ("waiting", "offered")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


async def _names(session: AsyncSession, service_ids: list) -> str:
    rows = dict((await session.execute(select(Service.id, Service.name).where(
        Service.id.in_([uuid.UUID(str(s)) for s in service_ids])))).all())
    return " + ".join(rows.get(uuid.UUID(str(s)), "service") for s in service_ids)


async def entry_out(session: AsyncSession, entry: WaitlistEntry) -> WaitlistOut:
    business = await session.get(Business, entry.business_id)
    return WaitlistOut(
        id=entry.id, business_name=business.name, business_slug=business.slug,
        visit=await _names(session, entry.service_ids), wanted_date=entry.wanted_date,
        earliest_time=entry.earliest_time, latest_time=entry.latest_time, status=entry.status,
        offered_starts_at=entry.offered_starts_at, offer_expires_at=entry.offer_expires_at,
    )


async def join(session: AsyncSession, client: Client, data: WaitlistJoin) -> WaitlistEntry:
    now = get_clock().now()
    if data.slot_id is not None:                       # a full class session
        slot = await session.get(Slot, data.slot_id)
        if slot is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That class session doesn't exist")
        business = await session.get(Business, slot.business_id)
        if slot.booked_count < slot.capacity and not slot.is_blocked:
            raise _conflict("This session still has seats. You can book it now.")
        tz = ZoneInfo(business.timezone)
        start_local, end_local = slot.starts_at.astimezone(tz), slot.ends_at.astimezone(tz)
        service_ids, wanted_date = [str(slot.service_id)], start_local.date()
        earliest = start_local.time()
        latest = end_local.time() if end_local.date() == wanted_date and end_local.time() > earliest else time(23, 59)
        starts_at = slot.starts_at
    else:                                              # an appointment
        first = await session.get(Service, data.service_ids[0])
        if first is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That service isn't available")
        business = await session.get(Business, first.business_id)
        _, _, options = await availability.available_times(session, business, data.service_ids, None, now)
        start, end = window(data.wanted_date, data.earliest_time, data.latest_time, business.timezone)
        if first_fit([o.starts_at for o in options], start, end):
            raise _conflict("There are free times in that window. You can book one now.")
        service_ids, wanted_date = [str(s) for s in data.service_ids], data.wanted_date
        earliest, latest, starts_at = data.earliest_time, data.latest_time, start

    if business.status != "live":
        raise _conflict("This business isn't taking bookings right now")
    if not (now < starts_at + timedelta(hours=24) and starts_at <= now + timedelta(hours=BOOKING_WINDOW_HOURS)):
        raise _conflict(f"You can join the waitlist for the next {BOOKING_WINDOW_HOURS // 24} days")
    active = await session.scalar(select(func.count()).select_from(WaitlistEntry).where(
        WaitlistEntry.client_id == client.id, WaitlistEntry.status.in_(ACTIVE)))
    if active >= MAX_ACTIVE_ENTRIES_PER_CLIENT:
        raise _conflict(f"You can be on up to {MAX_ACTIVE_ENTRIES_PER_CLIENT} waitlists at once")
    if await session.scalar(select(WaitlistEntry.id).where(
            WaitlistEntry.client_id == client.id, WaitlistEntry.business_id == business.id,
            WaitlistEntry.wanted_date == wanted_date, WaitlistEntry.status.in_(ACTIVE))):
        raise _conflict("You're already on this business's waitlist for that day")

    entry = WaitlistEntry(business_id=business.id, client_id=client.id, service_ids=service_ids, slot_id=data.slot_id,
                          wanted_date=wanted_date, earliest_time=earliest, latest_time=latest, status="waiting")
    session.add(entry)
    audit.record(session, actor_type="client", actor_id=client.auth_user_id, action="waitlist.joined",
                 business_id=business.id, details={"date": wanted_date.isoformat(), "class": data.slot_id is not None})
    await session.commit()
    await session.refresh(entry)
    return entry


async def leave(session: AsyncSession, client: Client, entry_id: uuid.UUID) -> None:
    entry = await session.scalar(select(WaitlistEntry).where(
        WaitlistEntry.id == entry_id, WaitlistEntry.client_id == client.id))
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Waitlist entry not found")
    if entry.status in ACTIVE:
        entry.status, entry.offered_starts_at, entry.offer_expires_at = "removed", None, None
        await session.commit()


async def offer_freed_time(session: AsyncSession, booking: Booking) -> int:
    """A booking was cancelled: offer its time to matching waiting clients. Returns how many were offered."""
    now = get_clock().now()
    business = await session.get(Business, booking.business_id)
    if business.status != "live":
        return 0
    tz = ZoneInfo(business.timezone)
    day = booking.starts_at.astimezone(tz).date()
    query = select(WaitlistEntry).where(
        WaitlistEntry.business_id == business.id, WaitlistEntry.wanted_date == day,
        WaitlistEntry.status == "waiting").order_by(WaitlistEntry.created_at).with_for_update(skip_locked=True)
    query = query.where(WaitlistEntry.slot_id == booking.slot_id) if booking.slot_id else \
        query.where(WaitlistEntry.slot_id.is_(None))
    offered = 0
    for entry in await session.scalars(query):
        if offered >= OFFERS_PER_OPENING:
            break
        if entry.slot_id is not None:
            starts_at = booking.starts_at
        else:
            try:
                _, _, options = await availability.available_times(
                    session, business, [uuid.UUID(s) for s in entry.service_ids], None, now)
            except HTTPException:
                continue                                  # e.g. a service was removed since
            start, end = window(entry.wanted_date, entry.earliest_time, entry.latest_time, business.timezone)
            starts_at = first_fit([o.starts_at for o in options], start, end)
            if starts_at is None:
                continue
        expires = offer_expiry(now, starts_at)
        if expires is None:
            continue
        entry.status, entry.offered_starts_at, entry.offer_expires_at = "offered", starts_at, expires
        client = await session.get(Client, entry.client_id)
        if client.email and client.email_verified_at:
            await enqueue(session, kind="waitlist_offer", to_address=client.email, recipient_type="client",
                          business_id=business.id, dedupe_key=f"waitlist_offer:{entry.id}:{starts_at.isoformat()}",
                          payload={"business_name": business.name, "visit": await _names(session, entry.service_ids),
                                   "when": local_time(starts_at, business.timezone),
                                   "expires": local_time(expires, business.timezone),
                                   "link": f"{get_settings().frontend_url.rstrip('/')}/my/waitlist"})
        offered += 1
    if offered:
        audit.record(session, actor_type="system", action="waitlist.offered", business_id=business.id,
                     booking_id=booking.id, details={"offers": offered})
    await session.commit()
    return offered


async def accepted_entry(session: AsyncSession, client: Client, entry_id: uuid.UUID) -> WaitlistEntry:
    """Check an offer can still be taken. The booking itself is made through the normal booking flow."""
    entry = await session.scalar(select(WaitlistEntry).where(
        WaitlistEntry.id == entry_id, WaitlistEntry.client_id == client.id).with_for_update())
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Waitlist entry not found")
    if entry.status != "offered" or get_clock().now() >= entry.offer_expires_at:
        raise _conflict("This offer has ended. You're still on the waitlist if a time opens up again.")
    return entry


async def mark_booked(session: AsyncSession, entry: WaitlistEntry, booking: Booking) -> None:
    entry.status, entry.booking_id = "booked", booking.id
    entry.offered_starts_at = entry.offer_expires_at = None
    await session.commit()


async def back_to_waiting(session: AsyncSession, entry: WaitlistEntry) -> None:
    entry.status, entry.offered_starts_at, entry.offer_expires_at = "waiting", None, None
    await session.commit()


async def tidy(session: AsyncSession) -> int:
    """Background job: finished offers go back to waiting; past days expire."""
    now = get_clock().now()
    changed = (await session.execute(update(WaitlistEntry).where(
        WaitlistEntry.status == "offered", WaitlistEntry.offer_expires_at <= now)
        .values(status="waiting", offered_starts_at=None, offer_expires_at=None))).rowcount
    changed += (await session.execute(update(WaitlistEntry).where(
        WaitlistEntry.status.in_(ACTIVE), WaitlistEntry.wanted_date < (now - timedelta(days=1)).date())
        .values(status="expired", offered_starts_at=None, offer_expires_at=None))).rowcount
    await session.commit()
    return changed