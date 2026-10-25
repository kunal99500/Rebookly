"""Turns weekly opening hours into exact bookable times. Pure functions: no database, easy to test.

Owners think in local time ("Mondays 7 to 12"); we store every slot in UTC. Converting day by day
with the business's time zone keeps slots correct across daylight-saving changes.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class WeeklyHours:
    weekday: int        # 0 = Monday ... 6 = Sunday
    start: time
    end: time


@dataclass(frozen=True)
class SlotTime:
    starts_at: datetime  # UTC
    ends_at: datetime    # UTC


def generate_slot_times(
    hours: list[WeeklyHours],
    duration_minutes: int,
    tz_name: str,
    first_day: date,
    days: int,
    now: datetime,
) -> list[SlotTime]:
    """Back-to-back slots of `duration_minutes` inside each opening period, for `days` days from `first_day`.

    Slots that start in the past, or wouldn't finish before closing time, are skipped.
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    tz = ZoneInfo(tz_name)
    length = timedelta(minutes=duration_minutes)
    slots: list[SlotTime] = []

    for offset in range(days):
        day = first_day + timedelta(days=offset)
        for period in (h for h in hours if h.weekday == day.weekday()):
            opens = datetime.combine(day, period.start, tzinfo=tz)
            closes = datetime.combine(day, period.end, tzinfo=tz)
            start = opens
            while start + length <= closes:
                start_utc = start.astimezone(timezone.utc)
                if start_utc > now:
                    slots.append(SlotTime(start_utc, (start + length).astimezone(timezone.utc)))
                start += length
    slots.sort(key=lambda s: s.starts_at)
    return slots


def check_no_overlaps(hours: list[WeeklyHours]) -> None:
    """Opening periods on the same day must not overlap (e.g. 9-13 and 12-17)."""
    for weekday in range(7):
        periods = sorted((h for h in hours if h.weekday == weekday), key=lambda h: h.start)
        for earlier, later in zip(periods, periods[1:]):
            if later.start < earlier.end:
                raise ValueError("Opening hours on the same day can't overlap")



@dataclass(frozen=True)
class BusyPeriod:
    slot_id: object       # the slot this booking is in
    starts_at: datetime
    ends_at: datetime


def remove_busy(slots: list, busy: list[BusyPeriod]) -> list:
    """Drop slots that overlap a booking in a *different* slot (one provider can't be in two places).

    Bookings in the same slot are already counted by booked_count, so group classes still work.
    """
    free = []
    for slot in slots:
        clash = any(
            b.slot_id != slot.id and slot.starts_at < b.ends_at and slot.ends_at > b.starts_at
            for b in busy
        )
        if not clash:
            free.append(slot)
    return free