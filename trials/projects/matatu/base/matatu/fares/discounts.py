"""Reductions for some riders."""

from ..config import RIDER_CHILD, RIDER_STUDENT, Settings
from ..money import percent_of


def rider_discount(rider: str, subtotal_kes: int, peak: bool, settings: Settings) -> int:
    if rider == RIDER_CHILD:
        return percent_of(subtotal_kes, settings.child_discount_percent)
    if rider == RIDER_STUDENT and not peak:
        return percent_of(subtotal_kes, settings.student_discount_percent)
    return 0
