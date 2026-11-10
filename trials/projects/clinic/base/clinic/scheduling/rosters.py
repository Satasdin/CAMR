"""When each doctor works."""

from typing import List, Optional

from ..clock import hour_of, moment_at, weekday_of
from ..errors import ValidationFailed
from ..models import Doctor, Shift
from ..store.repositories import get_doctor


def add_shift(store, doctor_id: str, weekday: int, start_hour: int, end_hour: int) -> Shift:
    get_doctor(store, doctor_id)
    if not 0 <= weekday <= 6:
        raise ValidationFailed(["weekday must be between 0 and 6"])
    if start_hour >= end_hour:
        raise ValidationFailed(["a shift must end after it starts"])
    shift = Shift(doctor_id=doctor_id, weekday=weekday, start_hour=start_hour, end_hour=end_hour)
    store.shifts.append(shift)
    return shift


def shifts_of(store, doctor_id: str) -> List[Shift]:
    return [s for s in store.shifts if s.doctor_id == doctor_id]


def shift_covering(store, doctor_id: str, moment: int) -> Optional[Shift]:
    weekday, hour = weekday_of(moment), hour_of(moment)
    for shift in shifts_of(store, doctor_id):
        if shift.weekday == weekday and shift.start_hour <= hour < shift.end_hour:
            return shift
    return None


def is_on_shift(store, doctor_id: str, moment: int) -> bool:
    return shift_covering(store, doctor_id, moment) is not None


def doctors_on(store, day: str) -> List[Doctor]:
    weekday = weekday_of(moment_at(day, 12))
    ids = sorted({s.doctor_id for s in store.shifts if s.weekday == weekday})
    return [get_doctor(store, doctor_id) for doctor_id in ids]
