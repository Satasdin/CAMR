"""Where the back office gets the time, so tests can control it."""

import calendar
import time
from datetime import datetime, timezone

from .config import LOCAL_OFFSET_HOURS, SECONDS_PER_HOUR


class SystemClock:
    def now(self) -> int:
        return int(time.time())


class FixedClock:
    """A clock that only moves when told to."""

    def __init__(self, start: int = 1_700_000_000):
        self.current = start

    def now(self) -> int:
        return self.current

    def advance(self, seconds: int) -> int:
        self.current += seconds
        return self.current


def hour_of(moment: int, offset_hours: int = LOCAL_OFFSET_HOURS) -> int:
    """The hour of the day at a moment, in local time."""
    return datetime.fromtimestamp(moment + offset_hours * SECONDS_PER_HOUR, tz=timezone.utc).hour


def weekday_of(moment: int, offset_hours: int = LOCAL_OFFSET_HOURS) -> int:
    """Monday is 0."""
    return datetime.fromtimestamp(moment + offset_hours * SECONDS_PER_HOUR, tz=timezone.utc).weekday()


def day_of(moment: int, offset_hours: int = LOCAL_OFFSET_HOURS) -> str:
    return datetime.fromtimestamp(moment + offset_hours * SECONDS_PER_HOUR, tz=timezone.utc).strftime("%Y-%m-%d")


OPERATING_DAY_START_HOUR = 3


def operating_day(moment: int, offset_hours: int = LOCAL_OFFSET_HOURS) -> str:
    """The operating day a moment belongs to, written YYYY-MM-DD."""
    return day_of(moment - OPERATING_DAY_START_HOUR * SECONDS_PER_HOUR, offset_hours)


def moment_of(day: str, hour: int, minute: int = 0, offset_hours: int = LOCAL_OFFSET_HOURS) -> int:
    """The moment of a local time on a day written YYYY-MM-DD."""
    parsed = datetime.strptime(day, "%Y-%m-%d")
    return calendar.timegm(parsed.timetuple()) + (hour - offset_hours) * SECONDS_PER_HOUR + minute * 60
