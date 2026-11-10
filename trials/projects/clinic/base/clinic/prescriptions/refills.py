"""Refilling prescriptions."""

from ..config import MAX_REFILLS
from ..errors import RefillsExhausted, ValidationFailed
from ..models import Prescription
from ..store.repositories import get_prescription, save_prescription


def set_refills(store, prescription_id: str, count: int) -> Prescription:
    if not 0 <= count <= MAX_REFILLS:
        raise ValidationFailed([f"refills must be between 0 and {MAX_REFILLS}"])
    prescription = get_prescription(store, prescription_id)
    prescription.refills_left = count
    return save_prescription(store, prescription)


def use_refill(store, prescription_id: str) -> Prescription:
    prescription = get_prescription(store, prescription_id)
    if not prescription.active:
        raise ValidationFailed([f"prescription {prescription_id} has ended"])
    if prescription.refills_left <= 0:
        raise RefillsExhausted(prescription_id)
    prescription.refills_left -= 1
    return save_prescription(store, prescription)
