"""Extra charges added on top of the band and weight prices."""

from typing import List, Tuple

from ..config import DEFAULT_SETTINGS, Settings
from ..models import Parcel
from ..money import percent_of
from .zones import is_remote

FRAGILE_CENTS = 15_000


def fuel_surcharge(subtotal_cents: int, settings: Settings) -> int:
    return percent_of(subtotal_cents, settings.fuel_percent)


def remote_area_surcharge(parcel: Parcel, settings: Settings) -> int:
    if is_remote(parcel.origin_zone) or is_remote(parcel.destination_zone):
        return settings.remote_area_cents
    return 0


def insurance_surcharge(parcel: Parcel, settings: Settings) -> int:
    return percent_of(parcel.insured_value_cents, settings.insurance_percent)


def surcharges_for(parcel: Parcel, subtotal_cents: int, settings: Settings = DEFAULT_SETTINGS) -> List[Tuple[str, int]]:
    """Every surcharge that applies, as (name, cents) pairs."""
    found = [("fuel", fuel_surcharge(subtotal_cents, settings))]
    remote = remote_area_surcharge(parcel, settings)
    if remote:
        found.append(("remote_area", remote))
    insurance = insurance_surcharge(parcel, settings)
    if insurance:
        found.append(("insurance", insurance))
    if parcel.fragile:
        found.append(("fragile", FRAGILE_CENTS))
    return found
