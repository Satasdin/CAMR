"""Combines every part of a price into one quote."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..config import DEFAULT_SETTINGS, Settings, service_level
from ..models import Customer, Parcel
from ..money import percent_of
from .discounts import discounts_for
from .rates import check_weight, weight_charge
from .surcharges import surcharges_for
from .zones import band, band_price


@dataclass
class Quote:
    lines: List[Tuple[str, int]]
    total_cents: int
    band: str

    def amount(self, name: str) -> int:
        return sum(cents for line, cents in self.lines if line == name)


def quote_parcel(parcel: Parcel, customer: Optional[Customer] = None, promo: str = "", settings: Settings = DEFAULT_SETTINGS) -> Quote:
    check_weight(parcel.weight_kg)
    which = band(parcel.origin_zone, parcel.destination_zone)
    level = service_level(parcel.service)

    lines: List[Tuple[str, int]] = [("base", band_price(parcel.origin_zone, parcel.destination_zone))]
    weight = weight_charge(parcel, which)
    if weight:
        lines.append(("weight", weight))

    subtotal = sum(cents for _, cents in lines)
    if level.multiplier_percent != 100:
        change = percent_of(subtotal, level.multiplier_percent) - subtotal
        lines.append((f"service {level.code}", change))
        subtotal += change

    lines.extend(surcharges_for(parcel, subtotal, settings))
    if customer is not None:
        lines.extend(discounts_for(customer, subtotal, promo))
    return Quote(lines=lines, total_cents=sum(cents for _, cents in lines), band=which)
