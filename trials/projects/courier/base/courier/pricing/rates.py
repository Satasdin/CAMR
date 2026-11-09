"""The weight part of a price."""

import math

from ..config import MAX_WEIGHT_KG, MIN_WEIGHT_KG, VOLUMETRIC_DIVISOR
from ..models import Parcel

PER_KG_CENTS = {"local": 3_000, "near": 5_500, "far": 8_500, "remote": 14_000}
FREE_WEIGHT_KG = 1


def volumetric_weight(parcel: Parcel) -> float:
    return (parcel.length_cm * parcel.width_cm * parcel.height_cm) / VOLUMETRIC_DIVISOR


def chargeable_weight(parcel: Parcel) -> int:
    """Whole kilograms, taken from whichever of the real and volumetric weights is larger."""
    return math.ceil(max(parcel.weight_kg, volumetric_weight(parcel)))


def check_weight(weight_kg: float) -> None:
    if weight_kg < MIN_WEIGHT_KG:
        raise ValueError(f"weight must be at least {MIN_WEIGHT_KG} kg")
    if weight_kg > MAX_WEIGHT_KG:
        raise ValueError(f"weight must be at most {MAX_WEIGHT_KG} kg")


def weight_charge(parcel: Parcel, band: str) -> int:
    extra = max(0, chargeable_weight(parcel) - FREE_WEIGHT_KG)
    return extra * PER_KG_CENTS[band]
