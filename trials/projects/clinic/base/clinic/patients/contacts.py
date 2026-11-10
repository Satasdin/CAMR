"""How a patient would like to be reached."""

from typing import List

from ..models import Patient
from ..store.repositories import get_patient, save_patient


def update_preferences(store, patient_id: str, wants_sms: bool, wants_email: bool) -> Patient:
    patient = get_patient(store, patient_id)
    patient.wants_sms = wants_sms
    patient.wants_email = wants_email
    return save_patient(store, patient)


def update_contact(store, patient_id: str, phone: str, email: str) -> Patient:
    patient = get_patient(store, patient_id)
    patient.phone = phone.strip()
    patient.email = email.strip()
    return save_patient(store, patient)


def reachable_channels(patient: Patient) -> List[str]:
    channels = []
    if patient.wants_sms and patient.phone:
        channels.append("sms")
    if patient.wants_email and patient.email:
        channels.append("email")
    return channels
