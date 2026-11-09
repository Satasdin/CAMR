"""Estimating when a parcel will arrive."""

from typing import Optional

from ..clock import day_of
from ..config import SECONDS_PER_DAY, service_level
from ..models import Parcel
from ..pricing.zones import band
from .status import is_finished

EXTRA_DAYS = {"local": 0, "near": 0, "far": 1, "remote": 2}


def transit_days(parcel: Parcel) -> int:
    level = service_level(parcel.service)
    return level.transit_days + EXTRA_DAYS[band(parcel.origin_zone, parcel.destination_zone)]


def estimated_arrival(parcel: Parcel) -> Optional[int]:
    if is_finished(parcel.status):
        return None
    return parcel.created_at + transit_days(parcel) * SECONDS_PER_DAY


def describe_arrival(parcel: Parcel) -> str:
    moment = estimated_arrival(parcel)
    if moment is None:
        return "Not expected: this parcel has finished its journey."
    return f"Expected by {day_of(moment)}."


def is_late(parcel: Parcel, now: int) -> bool:
    moment = estimated_arrival(parcel)
    return moment is not None and now > moment
