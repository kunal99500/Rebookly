"""When a booking may be moved to another time. Pure rules, no database.

Moving keeps the same hold and the same policy.
  * Client moves: only before the free-cancellation cutoff (otherwise "move late, then cancel free" would
    get around the policy). After that, the client contacts the business.
  * Owner moves: allowed any time before the appointment (e.g. a staff member is ill). Because the business
    changed the plan, the client may then cancel that booking without a fee.
The new time must fall within the hold's capture window, so the hold can still be collected at check-in.
"""
from datetime import datetime, timedelta

from app.rules.engine import Event

MOVED_BY_OWNER_REASON = ("You cancelled after the business moved your booking, so there's no fee. "
                         "The hold is released.")


def reschedule_problem(
    *, now: datetime, current_start: datetime, new_start: datetime,
    free_cancel_hours: int, honor_period_ends_at: datetime | None, by_owner: bool = False,
) -> str | None:
    """None if the move is allowed, otherwise a short reason that can be shown as it is."""
    if new_start == current_start:
        return "That's the time already booked"
    if new_start <= now:
        return "Please choose a time in the future"
    if by_owner:
        if current_start <= now:
            return "This appointment has already started"
    elif now >= current_start - timedelta(hours=free_cancel_hours):
        return ("It's too close to your appointment to move it online. "
                "Please contact the business, or cancel under the policy you agreed to.")
    if honor_period_ends_at is not None and new_start > honor_period_ends_at:
        return "That time is too far ahead for the current payment hold. Please choose an earlier time."
    return None


def engine_event_for_cancellation(event: Event, moved_by_owner: bool) -> Event:
    """A client cancelling a booking the business moved is treated, for money, like the business cancelling."""
    if event == Event.CLIENT_CANCELLED and moved_by_owner:
        return Event.OWNER_CANCELLED
    return event