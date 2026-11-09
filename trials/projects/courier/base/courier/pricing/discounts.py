"""Discounts that reduce a quote."""

from typing import List, Tuple

from ..models import Customer
from ..money import percent_of

LOYALTY_TIERS = ((5_000, 10), (2_000, 5), (500, 2))
PROMO_CODES = {"WELCOME10": 10, "RAINY5": 5}


def loyalty_percent(points: int) -> int:
    for threshold, percent in LOYALTY_TIERS:
        if points >= threshold:
            return percent
    return 0


def promo_percent(code: str) -> int:
    return PROMO_CODES.get(code.strip().upper(), 0)


def discounts_for(customer: Customer, subtotal_cents: int, promo: str = "") -> List[Tuple[str, int]]:
    """Only the larger of a loyalty and a promotional discount is applied."""
    loyalty = loyalty_percent(customer.loyalty_points)
    code = promo_percent(promo) if promo else 0
    if not loyalty and not code:
        return []
    if code > loyalty:
        return [(f"promo {promo.strip().upper()}", -percent_of(subtotal_cents, code))]
    return [("loyalty", -percent_of(subtotal_cents, loyalty))]
