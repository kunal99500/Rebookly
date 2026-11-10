"""Tests for flexible appointment times: any combination of services, any length."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.rules.availability import (
    Interval, WeeklyPeriod, combine_staff, opening_intervals, start_times, subtract,
)

UTC = timezone.utc
DAY = date(2026, 10, 19)  # a Monday
MIN = timedelta(minutes=1)


def at(h, m=0, day=DAY):
    return datetime(day.year, day.month, day.day, h, m, tzinfo=UTC)


def hhmm(times, tz="UTC"):
    return [t.astimezone(ZoneInfo(tz)).strftime("%H:%M") for t in times]


OPEN = [Interval(at(10), at(14))]
BOOKED = [Interval(at(11), at(11, 45))]
FREE = subtract(OPEN, BOOKED)
EARLY = at(0)
LATE = at(23)


def starts(minutes, cleanup=0, free=FREE, step=15, earliest=EARLY):
    return hhmm(start_times(free, minutes * MIN, (minutes + cleanup) * MIN, step * MIN, earliest, LATE, "UTC"))


def test_subtract_splits_around_a_booking():
    assert [(hhmm([i.start])[0], hhmm([i.end])[0]) for i in FREE] == [("10:00", "11:00"), ("11:45", "14:00")]


def test_haircut_30_minutes():
    assert starts(30) == ["10:00", "10:15", "10:30",
                          "11:45", "12:00", "12:15", "12:30", "12:45", "13:00", "13:15", "13:30"]


def test_haircut_and_wash_45_minutes_must_fit_completely():
    assert starts(45) == ["10:00", "10:15",
                          "11:45", "12:00", "12:15", "12:30", "12:45", "13:00", "13:15"]


def test_cleanup_time_keeps_a_gap_after_the_visit():
    # 30-minute visit + 15 minutes cleanup occupies 45 minutes, so 10:30 no longer fits before 11:00
    assert "10:30" not in starts(30, cleanup=15)
    assert "10:15" in starts(30, cleanup=15)


def test_starts_land_on_the_grid_even_after_odd_bookings():
    free = subtract(OPEN, [Interval(at(10), at(10, 50))])
    assert starts(30, free=free)[0] == "11:00"   # 10:50 rounds up to 11:00


def test_minimum_notice():
    assert starts(30, earliest=at(12, 5))[0] == "12:15"


def test_visit_too_long_for_any_gap():
    assert starts(300) == []


def test_time_off_is_removed_like_a_booking():
    free = subtract(FREE, [Interval(at(12), at(13))])   # lunch break
    times = starts(30, free=free)
    assert "12:15" not in times
    assert "11:45" not in times   # 11:45 + 30 = 12:15 runs into lunch
    assert "13:00" in times


def test_opening_hours_in_local_time_with_daylight_saving():
    # UK clocks go back on Sun 25 Oct 2026: 09:00 London is 08:00 UTC before, 09:00 UTC after.
    periods = [WeeklyPeriod(5, time(9), time(10)), WeeklyPeriod(0, time(9), time(10))]
    intervals = opening_intervals(periods, "Europe/London", date(2026, 10, 24), 3)
    assert [i.start.hour for i in intervals] == [8, 9]


def test_grid_follows_local_time_in_half_hour_time_zones():
    india_open = opening_intervals([WeeklyPeriod(0, time(9), time(11))], "Asia/Kolkata", DAY, 1)
    times = start_times(india_open, 60 * MIN, 60 * MIN, 30 * MIN, EARLY, LATE, "Asia/Kolkata")
    assert hhmm(times, "Asia/Kolkata") == ["09:00", "09:30", "10:00"]


def test_any_available_combines_staff():
    combined = combine_staff({"anna": [at(10), at(10, 15)], "ben": [at(10, 15), at(10, 30)]})
    assert combined == {at(10): ["anna"], at(10, 15): ["anna", "ben"], at(10, 30): ["ben"]}


def test_invalid_lengths_are_refused():
    with pytest.raises(ValueError):
        start_times(FREE, 30 * MIN, 15 * MIN, 15 * MIN, EARLY, LATE, "UTC")  # occupied shorter than visit


def test_naive_times_are_refused():
    with pytest.raises(ValueError):
        Interval(datetime(2026, 1, 1, 10), datetime(2026, 1, 1, 11))