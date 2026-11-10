"""Charges added after the fare itself has been rounded."""

from typing import List, Tuple

from ..config import Settings


def extras_for(raining: bool, settings: Settings) -> List[Tuple[str, int]]:
    """Every extra that applies, as (name, shillings) pairs."""
    found = []
    if raining:
        found.append(("rain", settings.rain_extra_kes))
    return found
