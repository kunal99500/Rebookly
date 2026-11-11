"""When a client may move a booking to another time. Pure rules, no database.

Moving keeps the same hold and the same policy. To stop "reschedule late, then cancel for free",
a booking can only be moved before its free-cancellation cutoff; after that, the client contacts the business.
The new time must also fall within the hold's capture window, so the hold can still be collected at check-in.
"""
from datetime import datetime, timedelta


def reschedule_problem(
    *, now: datetime, current_start: datetime, new_start: datetime,
    free_cancel_hours: int, honor_period_ends_at: datetime | None,
) -> str | None:
    """None if the move is allowed, otherwise a short reason the client can read."""
    if new_start == current_start:
        return "That's the time you already have"
    if new_start <= now:
        return "Please choose a time in the future"
    cutoff = current_start - timedelta(hours=free_cancel_hours)
    if now >= cutoff:
        return ("It's too close to your appointment to move it online. "
                "Please contact the business, or cancel under the policy you agreed to.")
    if honor_period_ends_at is not None and new_start > honor_period_ends_at:
        return "That time is too far ahead for your current payment hold. Please choose an earlier time."
    return None