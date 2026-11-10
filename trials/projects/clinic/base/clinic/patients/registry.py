"""Registering patients and finding them again."""

from typing import List, Optional

from ..config import MIN_NAME_LENGTH
from ..errors import ValidationFailed
from ..models import Patient
from ..store.repositories import get_patient, save_patient


def register_patient(store, name: str, phone: str, email: str, date_of_birth: str, clock) -> Patient:
    if len(name.strip()) < MIN_NAME_LENGTH:
        raise ValidationFailed(["a patient needs a name"])
    if phone and find_by_phone(store, phone) is not None:
        raise ValidationFailed([f"{phone} is already registered"])
    patient = Patient(id=store.next_id("PAT"), name=name.strip(), phone=phone.strip(), email=email.strip(),
                      date_of_birth=date_of_birth, created_at=clock.now())
    return save_patient(store, patient)


def find_by_phone(store, phone: str) -> Optional[Patient]:
    for patient in store.patients.values():
        if patient.phone == phone:
            return patient
    return None


def search_by_name(store, fragment: str) -> List[Patient]:
    needle = fragment.strip().lower()
    return sorted((p for p in store.patients.values() if needle in p.name.lower()), key=lambda p: p.name)


def deactivate_patient(store, patient_id: str) -> Patient:
    patient = get_patient(store, patient_id)
    patient.active = False
    return save_patient(store, patient)
