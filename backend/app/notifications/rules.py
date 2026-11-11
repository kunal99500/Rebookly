"""When to remind, and how long to wait before retrying a failed send. Pure functions."""
from datetime import datetime, timedelta

RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2))
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


def next_attempt(attempts_so_far: int, now: datetime) -> datetime | None:
    """After a failed send: when to try again, or None to give up."""
    if attempts_so_far >= MAX_ATTEMPTS:
        return None
    return now + RETRY_DELAYS[min(attempts_so_far - 1, len(RETRY_DELAYS) - 1)]


def reminder_due(*, starts_at: datetime, booked_at: datetime, now: datetime) -> str | None:
    """Which reminder (if any) should go out now.

    One reminder per booking: 24 hours before, or 2 hours before for bookings made less than a day ahead.
    The job runs every few minutes, so each window is checked with some slack.
    """
    until_start = starts_at - now
    if until_start <= timedelta(0):
        return None
    if starts_at - booked_at > timedelta(hours=25):
        return "reminder_24h" if until_start <= timedelta(hours=24) else None
    if starts_at - booked_at > timedelta(hours=2, minutes=30):
        return "reminder_2h" if until_start <= timedelta(hours=2) else None
    return None   # booked very close to the start: the confirmation is reminder enough