"""The wording of reminders."""

from ..clock import day_of, time_of
from ..config import DEFAULT_SETTINGS, Settings
from ..models import Appointment, Doctor, Patient


def location_line(doctor: Doctor) -> str:
    return f"{doctor.name}, {doctor.department}, room {doctor.room}"


def email_subject(appointment: Appointment, settings: Settings = DEFAULT_SETTINGS) -> str:
    return f"{settings.clinic_name}: your appointment on {day_of(appointment.start_at)}"


def email_body(patient: Patient, doctor: Doctor, appointment: Appointment, settings: Settings = DEFAULT_SETTINGS) -> str:
    return "\n".join([
        f"Dear {patient.first_name},",
        f"You have an appointment on {day_of(appointment.start_at)} at {time_of(appointment.start_at)}.",
        f"You will be seen by: {location_line(doctor)}.",
        f"Reason for visit: {appointment.reason}",
        f"Booking reference: {appointment.id}",
        f"To change it, call {settings.front_desk_phone}.",
    ])


def sms_body(patient: Patient, doctor: Doctor, appointment: Appointment, settings: Settings = DEFAULT_SETTINGS) -> str:
    return (f"{patient.first_name}, you have an appointment on {day_of(appointment.start_at)} at "
            f"{time_of(appointment.start_at)} with {location_line(doctor)}. "
            f"Booking reference {appointment.id}. To change it, call {settings.front_desk_phone}.")
