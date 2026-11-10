"""Deciding who is reminded about an appointment, and how."""

from typing import List

from ..config import REMINDER_WINDOW_HOURS, SECONDS_PER_HOUR
from ..models import APPOINTMENT_BOOKED, Appointment, Doctor, Message, Patient
from ..store.repositories import get_doctor, get_patient, save_appointment
from .templates import email_body, email_subject, sms_body


def due_for_reminder(appointment: Appointment, now: int) -> bool:
    if appointment.status != APPOINTMENT_BOOKED or appointment.reminded:
        return False
    return now < appointment.start_at <= now + REMINDER_WINDOW_HOURS * SECONDS_PER_HOUR


def messages_for(patient: Patient, doctor: Doctor, appointment: Appointment, now: int) -> List[Message]:
    out = []
    if patient.wants_email and patient.email:
        out.append(Message(channel="email", to=patient.email, subject=email_subject(appointment),
                           body=email_body(patient, doctor, appointment), sent_at=now))
    if patient.wants_sms and patient.phone:
        out.append(Message(channel="sms", to=patient.phone, body=sms_body(patient, doctor, appointment), sent_at=now))
    return out


def send_reminders(store, sender, clock) -> int:
    """Sends reminders for every appointment coming up and returns how many messages went out."""
    now = clock.now()
    count = 0
    for appointment in list(store.appointments.values()):
        if not due_for_reminder(appointment, now):
            continue
        patient = get_patient(store, appointment.patient_id)
        doctor = get_doctor(store, appointment.doctor_id)
        count += sum(1 for message in messages_for(patient, doctor, appointment, now) if sender.send(message))
        appointment.reminded = True
        save_appointment(store, appointment)
    return count
