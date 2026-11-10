"""Writing prescriptions."""

from typing import List

from ..errors import AllergyConflict, InteractionConflict, ValidationFailed
from ..models import Patient, Prescription
from ..patients.allergies import is_allergic
from ..store.repositories import get_doctor, get_patient, get_prescription, prescriptions_of, save_prescription
from .dosing import check_single_dose, paediatric_dose
from .formulary import Drug, get_drug
from .interactions import first_clash


def active_for(store, patient_id: str) -> List[Prescription]:
    return [p for p in prescriptions_of(store, patient_id) if p.active]


def check_safe(store, patient: Patient, drug: Drug) -> None:
    if is_allergic(patient, drug.ingredient):
        raise AllergyConflict(patient.id, drug.ingredient)
    current = [get_drug(p.drug_code).ingredient for p in active_for(store, patient.id)]
    other = first_clash(drug.ingredient, current)
    if other is not None:
        raise InteractionConflict(drug.ingredient, other)


def prescribe(store, patient_id: str, doctor_id: str, drug_code: str, dose_mg: float, days: int, clock,
              doses_per_day: int = 1, refills: int = 0) -> Prescription:
    patient = get_patient(store, patient_id)
    get_doctor(store, doctor_id)
    drug = get_drug(drug_code)
    if days <= 0:
        raise ValidationFailed(["a prescription must last at least one day"])
    check_single_dose(drug, dose_mg)
    check_safe(store, patient, drug)
    prescription = Prescription(id=store.next_id("RX"), patient_id=patient_id, doctor_id=doctor_id, drug_code=drug_code,
                                dose_mg=dose_mg, days=days, doses_per_day=doses_per_day, refills_left=refills,
                                created_at=clock.now())
    return save_prescription(store, prescription)


def prescribe_for_child(store, patient_id: str, doctor_id: str, drug_code: str, weight_kg: float, days: int, clock,
                        doses_per_day: int = 1, refills: int = 0) -> Prescription:
    dose_mg = paediatric_dose(drug_code, weight_kg)
    return prescribe(store, patient_id, doctor_id, drug_code, dose_mg, days, clock,
                     doses_per_day=doses_per_day, refills=refills)


def end_prescription(store, prescription_id: str) -> Prescription:
    prescription = get_prescription(store, prescription_id)
    prescription.active = False
    return save_prescription(store, prescription)
