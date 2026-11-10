"""Charges added after the fare itself has been rounded."""

from typing import List, Tuple

from ..config import Settings

LUGGAGE_PER_BAG_KES = 20


def extras_for(raining: bool, settings: Settings, bags: int = 0) -> List[Tuple[str, int]]:
    """Every extra that applies, as (name, shillings) pairs."""
    found = []
    if raining:
        found.append(("rain", settings.rain_extra_kes))
    if bags > 1:
        found.append(("luggage", (bags - 1) * LUGGAGE_PER_BAG_KES))
    return found
