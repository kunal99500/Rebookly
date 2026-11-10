"""Free start times for a visit of any length. Pure functions: no database, easy to test.

The idea, for one staff member on one day:
    opening hours  -  bookings (including cleanup)  -  time off   =  free periods
    then offer every start time on the step grid (e.g. every 15 min) where the whole visit fits.

All times are timezone-aware. Opening hours are local; everything else is UTC.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Interval times must be timezone-aware")


@dataclass(frozen=True)
class WeeklyPeriod:
    weekday: int    # 0 = Monday ... 6 = Sunday
    start: time     # local time
    end: time


def opening_intervals(periods: list[WeeklyPeriod], tz_name: str, first_day: date, days: int) -> list[Interval]:
    """Weekly local hours -> concrete UTC intervals. Converting day by day keeps daylight-saving correct."""
    tz = ZoneInfo(tz_name)
    result = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        for p in periods:
            if p.weekday == day.weekday():
                result.append(Interval(
                    datetime.combine(day, p.start, tzinfo=tz).astimezone(timezone.utc),
                    datetime.combine(day, p.end, tzinfo=tz).astimezone(timezone.utc),
                ))
    return sorted(result, key=lambda i: i.start)


def subtract(free: list[Interval], busy: list[Interval]) -> list[Interval]:
    """Remove every busy interval from the free intervals."""
    result = []
    for f in free:
        pieces = [f]
        for b in busy:
            next_pieces = []
            for piece in pieces:
                if b.end <= piece.start or b.start >= piece.end:   # no overlap
                    next_pieces.append(piece)
                    continue
                if b.start > piece.start:
                    next_pieces.append(Interval(piece.start, b.start))
                if b.end < piece.end:
                    next_pieces.append(Interval(b.end, piece.end))
            pieces = next_pieces
        result.extend(pieces)
    return sorted(result, key=lambda i: i.start)


def _next_grid_time(moment: datetime, step: timedelta, tz: ZoneInfo) -> datetime:
    """Round up to the step grid counted from local midnight (so starts land on :00, :15, :30, :45)."""
    local = moment.astimezone(tz)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = local - midnight
    steps = -(-elapsed // step)  # ceiling division
    return (midnight + steps * step).astimezone(timezone.utc)


def start_times(
    free: list[Interval], visit: timedelta, occupied: timedelta, step: timedelta,
    earliest: datetime, latest_start: datetime, tz_name: str,
) -> list[datetime]:
    """Start times where the visit (plus cleanup) fits completely inside a free interval.

    visit:        what the client books (e.g. 45 min)
    occupied:     visit + cleanup time (how long the staff member is unavailable)
    earliest:     now + minimum notice
    latest_start: end of the booking window
    """
    if visit <= timedelta(0) or occupied < visit or step <= timedelta(0):
        raise ValueError("Invalid visit, cleanup or step length")
    tz = ZoneInfo(tz_name)
    starts = []
    for f in free:
        candidate = _next_grid_time(max(f.start, earliest), step, tz)
        while candidate + occupied <= f.end and candidate <= latest_start:
            starts.append(candidate)
            candidate += step
    return sorted(set(starts))


def combine_staff(per_staff: dict[object, list[datetime]]) -> dict[datetime, list[object]]:
    """For "any available": each start time with the staff members free then (in the given order)."""
    combined: dict[datetime, list[object]] = {}
    for staff_id, times in per_staff.items():
        for t in times:
            combined.setdefault(t, []).append(staff_id)
    return dict(sorted(combined.items()))