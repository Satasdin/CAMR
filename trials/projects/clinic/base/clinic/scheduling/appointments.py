"""Booking appointments and moving them through a visit."""

from typing import List

from ..config import MAX_ADVANCE_BOOKING_DAYS, SECONDS_PER_DAY, SLOT_MINUTES
from ..errors import InvalidTransition, OutsideRoster, SlotTaken, ValidationFailed
from ..models import (APPOINTMENT_BOOKED, APPOINTMENT_CHECKED_IN, APPOINTMENT_COMPLETED, APPOINTMENT_NO_SHOW,
                      Appointment)
from ..store.repositories import appointments_of_patient, get_appointment, get_doctor, get_patient, save_appointment
from .rosters import is_on_shift
from .slots import is_blocked, is_on_grid, taken_starts


def check_bookable(store, doctor_id: str, start_at: int, now: int) -> None:
    if start_at <= now:
        raise ValidationFailed(["an appointment must be in the future"])
    if start_at > now + MAX_ADVANCE_BOOKING_DAYS * SECONDS_PER_DAY:
        raise ValidationFailed([f"appointments can be booked up to {MAX_ADVANCE_BOOKING_DAYS} days ahead"])
    if not is_on_grid(start_at):
        raise ValidationFailed([f"appointments start on {SLOT_MINUTES} minute slots"])
    if is_blocked(start_at):
        raise ValidationFailed(["no appointments are offered at that time"])
    if not is_on_shift(store, doctor_id, start_at):
        raise OutsideRoster(doctor_id, start_at)
    if start_at in taken_starts(store, doctor_id):
        raise SlotTaken(doctor_id, start_at)


def book_appointment(store, patient_id: str, doctor_id: str, start_at: int, reason: str, clock) -> Appointment:
    get_patient(store, patient_id)
    get_doctor(store, doctor_id)
    now = clock.now()
    check_bookable(store, doctor_id, start_at, now)
    appointment = Appointment(id=store.next_id("APT"), patient_id=patient_id, doctor_id=doctor_id,
                              start_at=start_at, reason=reason, minutes=SLOT_MINUTES, created_at=now)
    return save_appointment(store, appointment)


def _move(store, appointment_id: str, expected: str, wanted: str) -> Appointment:
    appointment = get_appointment(store, appointment_id)
    if appointment.status != expected:
        raise InvalidTransition(appointment.status, wanted)
    appointment.status = wanted
    return save_appointment(store, appointment)


def check_in(store, appointment_id: str, clock) -> Appointment:
    appointment = _move(store, appointment_id, APPOINTMENT_BOOKED, APPOINTMENT_CHECKED_IN)
    appointment.checked_in_at = clock.now()
    return save_appointment(store, appointment)


def complete_visit(store, appointment_id: str) -> Appointment:
    return _move(store, appointment_id, APPOINTMENT_CHECKED_IN, APPOINTMENT_COMPLETED)


def mark_no_show(store, appointment_id: str) -> Appointment:
    return _move(store, appointment_id, APPOINTMENT_BOOKED, APPOINTMENT_NO_SHOW)


def upcoming_for(store, patient_id: str, now: int) -> List[Appointment]:
    found = [a for a in appointments_of_patient(store, patient_id) if a.status == APPOINTMENT_BOOKED and a.start_at > now]
    return sorted(found, key=lambda a: a.start_at)
