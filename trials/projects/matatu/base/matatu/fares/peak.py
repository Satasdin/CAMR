"""Which hours cost more."""

from ..clock import hour_of, weekday_of

PEAK_WINDOWS = ((6, 9), (16, 19))


def is_peak_hour(hour: int) -> bool:
    return any(start <= hour < end for start, end in PEAK_WINDOWS)


def is_peak(moment: int) -> bool:
    return weekday_of(moment) < 5 and is_peak_hour(hour_of(moment))
