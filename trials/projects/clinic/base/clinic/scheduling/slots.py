"""Working out which appointment times can be offered."""

from typing import Dict, List, Set, Tuple

from ..clock import hour_of, moment_at, weekday_of
from ..config import CLINIC_CLOSE_HOUR, CLINIC_OPEN_HOUR, SECONDS_PER_HOUR, SECONDS_PER_MINUTE, SLOT_MINUTES
from ..models import APPOINTMENT_BOOKED, APPOINTMENT_CHECKED_IN
from ..store.repositories import appointments_of_doctor
from .rosters import is_on_shift

WEEKLY_BLOCKS: Dict[int, Tuple[int, int]] = {2: (13, 15)}


def is_blocked(moment: int) -> bool:
    block = WEEKLY_BLOCKS.get(weekday_of(moment))
    return block is not None and block[0] <= hour_of(moment) < block[1]


def slots_on(day: str) -> List[int]:
    first = moment_at(day, CLINIC_OPEN_HOUR)
    last = moment_at(day, CLINIC_CLOSE_HOUR)
    return list(range(first, last, SLOT_MINUTES * SECONDS_PER_MINUTE))


def is_on_grid(moment: int) -> bool:
    return (moment % SECONDS_PER_HOUR) % (SLOT_MINUTES * SECONDS_PER_MINUTE) == 0


def taken_starts(store, doctor_id: str) -> Set[int]:
    live = (APPOINTMENT_BOOKED, APPOINTMENT_CHECKED_IN)
    return {a.start_at for a in appointments_of_doctor(store, doctor_id) if a.status in live}


def open_slots(store, doctor_id: str, day: str) -> List[int]:
    taken = taken_starts(store, doctor_id)
    return [slot for slot in slots_on(day)
            if slot not in taken and is_on_shift(store, doctor_id, slot) and not is_blocked(slot)]
