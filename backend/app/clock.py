"""The app's single source of time.

Rule: never call datetime.now() anywhere else in the code. Always use get_clock().now().
In production this is real UTC time. In development it can be fast-forwarded for demos.
"""
from datetime import datetime, timedelta, timezone
from threading import Lock


class Clock:
    """Real time, always in UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class SimulatedClock(Clock):
    """Real time plus an adjustable offset. Development and demos only."""

    MAX_OFFSET = timedelta(days=30)

    def __init__(self) -> None:
        self._offset = timedelta(0)
        self._lock = Lock()

    def now(self) -> datetime:
        return datetime.now(timezone.utc) + self._offset

    @property
    def offset(self) -> timedelta:
        return self._offset

    def advance(self, delta: timedelta) -> datetime:
        """Move time forward (or back, with a negative delta)."""
        with self._lock:
            new_offset = self._offset + delta
            if abs(new_offset) > self.MAX_OFFSET:
                raise ValueError("Simulated clock can't move more than 30 days from real time")
            self._offset = new_offset
        return self.now()

    def set_to(self, target: datetime) -> datetime:
        """Jump to an exact moment, e.g. 5 minutes after an appointment starts."""
        if target.tzinfo is None:
            raise ValueError("target must be timezone-aware")
        return self.advance(target - self.now())

    def reset(self) -> datetime:
        with self._lock:
            self._offset = timedelta(0)
        return self.now()


_clock: Clock | None = None


def init_clock(simulated: bool) -> Clock:
    """Called once when the server starts, based on the SIMULATED_CLOCK setting."""
    global _clock
    _clock = SimulatedClock() if simulated else Clock()
    return _clock


def get_clock() -> Clock:
    if _clock is None:
        raise RuntimeError("Clock not initialised. Call init_clock() at startup.")
    return _clock