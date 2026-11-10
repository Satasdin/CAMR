"""What each kind of visit costs."""

from typing import Dict, List, Tuple

from ..config import LATE_CANCEL_FEE_CENTS
from ..models import APPOINTMENT_CANCELLED, Appointment, Doctor

CONSULTATION_CENTS: Dict[str, int] = {
    "General Medicine": 150_000,
    "Cardiology": 350_000,
    "Oncology": 450_000,
    "Paediatrics": 200_000,
    "Dermatology": 250_000,
}
DEFAULT_CONSULTATION_CENTS = 150_000


def consultation_cents(department: str) -> int:
    return CONSULTATION_CENTS.get(department, DEFAULT_CONSULTATION_CENTS)


def lines_for(appointment: Appointment, doctor: Doctor) -> List[Tuple[str, int]]:
    """The (description, cents) lines an appointment is billed for."""
    if appointment.status == APPOINTMENT_CANCELLED:
        return [("Late cancellation fee", LATE_CANCEL_FEE_CENTS)] if appointment.late_cancel else []
    return [(f"{doctor.department} consultation", consultation_cents(doctor.department))]
