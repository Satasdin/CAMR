"""What is printed on a bottle."""

from ..errors import ValidationFailed
from ..models import Patient, Prescription
from .formulary import Drug


def volume_ml(prescription: Prescription, drug: Drug) -> float:
    """How many millilitres one dose comes to."""
    if drug.mg_per_ml <= 0:
        raise ValidationFailed([f"{drug.name} is not a liquid"])
    return prescription.dose_mg / drug.mg_per_ml


def label_text(prescription: Prescription, drug: Drug, patient: Patient) -> str:
    volume = volume_ml(prescription, drug)
    return "\n".join([
        patient.name,
        drug.name,
        f"Take {volume:.1f} ml, {prescription.doses_per_day} time(s) a day for {prescription.days} days",
    ])
