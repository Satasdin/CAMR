"""What a patient must not be given."""

from typing import List

from ..models import Patient
from ..store.repositories import get_patient, save_patient


def normalise(ingredient: str) -> str:
    return ingredient.strip().lower()


def add_allergy(store, patient_id: str, ingredient: str) -> Patient:
    patient = get_patient(store, patient_id)
    wanted = normalise(ingredient)
    if wanted not in [normalise(known) for known in patient.allergies]:
        patient.allergies.append(wanted)
    return save_patient(store, patient)


def remove_allergy(store, patient_id: str, ingredient: str) -> Patient:
    patient = get_patient(store, patient_id)
    unwanted = normalise(ingredient)
    patient.allergies = [known for known in patient.allergies if normalise(known) != unwanted]
    return save_patient(store, patient)


def is_allergic(patient: Patient, ingredient: str) -> bool:
    return normalise(ingredient) in [normalise(known) for known in patient.allergies]


def allergy_list(patient: Patient) -> List[str]:
    return sorted(normalise(known) for known in patient.allergies)
