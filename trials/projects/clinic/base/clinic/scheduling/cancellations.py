"""Cancelling appointments."""

from ..config import CANCEL_NOTICE_HOURS, SECONDS_PER_HOUR
from ..errors import InvalidTransition
from ..models import APPOINTMENT_BOOKED, APPOINTMENT_CANCELLED, Appointment
from ..store.repositories import get_appointment, save_appointment
from .waitlist import offer_next


def is_late(appointment: Appointment, now: int) -> bool:
    return appointment.start_at - now < CANCEL_NOTICE_HOURS * SECONDS_PER_HOUR


def cancel_appointment(store, appointment_id: str, clock) -> Appointment:
    appointment = get_appointment(store, appointment_id)
    if appointment.status != APPOINTMENT_BOOKED:
        raise InvalidTransition(appointment.status, APPOINTMENT_CANCELLED)
    now = clock.now()
    appointment.status = APPOINTMENT_CANCELLED
    appointment.cancelled_at = now
    appointment.late_cancel = is_late(appointment, now)
    save_appointment(store, appointment)
    offer_next(store, appointment.doctor_id, appointment.start_at, clock)
    return appointment
