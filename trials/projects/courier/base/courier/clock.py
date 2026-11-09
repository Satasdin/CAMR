"""Where the service gets the time, so tests can control it."""

import time
from datetime import datetime, timezone


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


def hour_of(moment: int, offset_hours: int = 3) -> int:
    """The hour of the day at a moment, in the service's local time."""
    return datetime.fromtimestamp(moment + offset_hours * 3600, tz=timezone.utc).hour


def day_of(moment: int, offset_hours: int = 3) -> str:
    return datetime.fromtimestamp(moment + offset_hours * 3600, tz=timezone.utc).strftime("%Y-%m-%d")
