"""Waitlist rules: when to offer a freed time, to whom, and when a cancelled time counts as refilled.
Pure functions, no database."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MAX_ACTIVE_ENTRIES_PER_CLIENT = 3
OFFERS_PER_OPENING = 3                    # notify a few people; the first to book gets it
OFFER_MINUTES = 30
LAST_OFFER_BEFORE_START = timedelta(minutes=30)


def window(wanted_date: date, earliest: time, latest: time, timezone: str) -> tuple[datetime, datetime]:
    """The client's wished-for window (local date and times) as exact moments."""
    tz = ZoneInfo(timezone)
    return datetime.combine(wanted_date, earliest, tz), datetime.combine(wanted_date, latest, tz)


def first_fit(starts: list[datetime], window_start: datetime, window_end: datetime) -> datetime | None:
    """The earliest available start inside the client's window (the visit must START inside it)."""
    fitting = sorted(s for s in starts if window_start <= s < window_end)
    return fitting[0] if fitting else None


def offer_expiry(now: datetime, starts_at: datetime) -> datetime | None:
    """How long an offer stays open: 30 minutes, but never past 30 minutes before the appointment."""
    last_moment = starts_at - LAST_OFFER_BEFORE_START
    if last_moment <= now:
        return None                        # too late to offer this time to anyone
    return min(now + timedelta(minutes=OFFER_MINUTES), last_moment)


def is_refill(*, cancelled_at: datetime, freed_start: datetime, freed_end: datetime,
              freed_staff_id, freed_slot_id, new_start: datetime, new_end: datetime,
              new_staff_id, new_slot_id, new_created_at: datetime) -> bool:
    """Did a NEW booking take the time a cancelled booking freed?

    Appointments: same staff member, and the new visit overlaps the freed time.
    Classes: a new seat in the same session.
    Only bookings made after the cancellation count.
    """
    if new_created_at <= cancelled_at:
        return False
    if freed_slot_id is not None:
        return new_slot_id == freed_slot_id
    return new_staff_id == freed_staff_id and new_start < freed_end and new_end > freed_start