"""Putting a fare together."""

from dataclasses import dataclass, field
from typing import List, Tuple

from ..config import DEFAULT_SETTINGS, FARE_ROUNDING_KES, MAX_FARE_KES, MIN_FARE_KES, RIDER_ADULT, Settings
from ..money import percent_of, round_up_to
from .bands import band_for
from .discounts import rider_discount
from .extras import extras_for
from .peak import is_peak


@dataclass
class FareQuote:
    band: str
    peak: bool
    lines: List[Tuple[str, int]] = field(default_factory=list)

    @property
    def total_kes(self) -> int:
        return sum(amount for _, amount in self.lines)

    def amount(self, name: str) -> int:
        return sum(amount for line, amount in self.lines if line == name)


def quote_fare(stages: int, moment: int, rider: str = RIDER_ADULT, bags: int = 0, raining: bool = False,
               settings: Settings = DEFAULT_SETTINGS) -> FareQuote:
    """The fare for one passenger travelling this many stages at this moment."""
    band = band_for(stages)
    peak = is_peak(moment)
    subtotal = percent_of(band.fare_kes, settings.peak_percent) if peak else band.fare_kes
    subtotal -= rider_discount(rider, subtotal, peak, settings)
    fare = min(MAX_FARE_KES, max(MIN_FARE_KES, round_up_to(subtotal, FARE_ROUNDING_KES)))
    result = FareQuote(band=band.code, peak=peak, lines=[("fare", fare)])
    result.lines.extend(extras_for(raining, settings, bags))
    return result
