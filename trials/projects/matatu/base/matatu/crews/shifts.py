"""Who was on which vehicle, and when."""

from typing import List

from ..clock import day_of
from ..models import Shift
from ..store.repositories import get_crew_member, get_shift, get_vehicle, save_shift


def start_shift(store, crew_id: str, vehicle_id: str, clock) -> Shift:
    get_crew_member(store, crew_id)
    get_vehicle(store, vehicle_id)
    return save_shift(store, Shift(id=store.next_id("SFT"), crew_id=crew_id, vehicle_id=vehicle_id,
                                   started_at=clock.now()))


def end_shift(store, shift_id: str, clock) -> Shift:
    shift = get_shift(store, shift_id)
    shift.ended_at = clock.now()
    return save_shift(store, shift)


def shifts_on(store, day: str) -> List[Shift]:
    return [shift for shift in store.shifts.values() if day_of(shift.started_at) == day]
