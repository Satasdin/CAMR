"""Checking how much of a drug is prescribed."""

from ..errors import ValidationFailed
from ..models import Prescription
from .formulary import Drug


def check_single_dose(drug: Drug, dose_mg: float) -> None:
    if dose_mg <= 0:
        raise ValidationFailed(["a dose must be more than zero"])
    if drug.max_single_mg and dose_mg > drug.max_single_mg:
        raise ValidationFailed([f"{drug.name} is limited to {drug.max_single_mg} mg at a time"])


def daily_total(dose_mg: float, doses_per_day: int) -> float:
    return dose_mg * doses_per_day


def course_total(prescription: Prescription) -> float:
    return daily_total(prescription.dose_mg, prescription.doses_per_day) * prescription.days


def tablets_per_dose(drug: Drug, dose_mg: float) -> float:
    if drug.form != "tablet":
        raise ValidationFailed([f"{drug.name} is not a tablet"])
    return dose_mg / drug.strength_mg
