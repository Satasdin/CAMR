"""Where the service gets the time, so tests can control it."""

import time
from datetime import datetime, timezone

LOCAL_OFFSET_HOURS = 3


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


def _local(moment: int) -> datetime:
    return datetime.fromtimestamp(moment + LOCAL_OFFSET_HOURS * 3600, tz=timezone.utc)


def hour_of(moment: int) -> int:
    """The hour of the day at a moment, in the clinic's local time."""
    return _local(moment).hour


def day_of(moment: int) -> str:
    return _local(moment).strftime("%Y-%m-%d")


def time_of(moment: int) -> str:
    return _local(moment).strftime("%H:%M")


def weekday_of(moment: int) -> int:
    """Monday is 0 and Sunday is 6."""
    return _local(moment).weekday()


def moment_at(day: str, hour: int, minute: int = 0) -> int:
    """The moment of a local date and time, such as '2024-03-05' at 10:40."""
    local = datetime.strptime(day, "%Y-%m-%d").replace(hour=hour, minute=minute, tzinfo=timezone.utc)
    return int(local.timestamp()) - LOCAL_OFFSET_HOURS * 3600
