"""The records the clinic keeps."""

from dataclasses import dataclass, field
from typing import List, Optional

APPOINTMENT_BOOKED = "booked"
APPOINTMENT_CHECKED_IN = "checked_in"
APPOINTMENT_COMPLETED = "completed"
APPOINTMENT_CANCELLED = "cancelled"
APPOINTMENT_NO_SHOW = "no_show"

INVOICE_OPEN = "open"
INVOICE_PAID = "paid"
INVOICE_VOID = "void"

TRIAGE_WAITING = "waiting"
TRIAGE_SEEN = "seen"

CLAIM_SUBMITTED = "submitted"
CLAIM_SETTLED = "settled"
CLAIM_REJECTED = "rejected"


@dataclass
class Patient:
    id: str
    name: str
    phone: str = ""
    email: str = ""
    date_of_birth: str = ""
    allergies: List[str] = field(default_factory=list)
    wants_sms: bool = True
    wants_email: bool = True
    active: bool = True
    created_at: int = 0

    @property
    def first_name(self) -> str:
        return self.name.split()[0] if self.name.split() else ""


@dataclass
class Doctor:
    id: str
    name: str
    department: str
    room: str = ""
    active: bool = True


@dataclass
class Shift:
    doctor_id: str
    weekday: int
    start_hour: int
    end_hour: int


@dataclass
class Appointment:
    id: str
    patient_id: str
    doctor_id: str
    start_at: int
    reason: str = ""
    minutes: int = 20
    status: str = APPOINTMENT_BOOKED
    reminded: bool = False
    late_cancel: bool = False
    created_at: int = 0
    cancelled_at: Optional[int] = None
    checked_in_at: Optional[int] = None


@dataclass
class WaitlistEntry:
    id: str
    patient_id: str
    doctor_id: str
    added_at: int
    offered_start: Optional[int] = None
    offer_expires_at: Optional[int] = None


@dataclass
class Vitals:
    temperature_c: float = 37.0
    heart_rate: int = 75
    breaths_per_minute: int = 16
    systolic: int = 120
    spo2: int = 98


@dataclass
class TriageCase:
    id: str
    patient_id: str
    vitals: Vitals
    score: int
    level: str
    arrived_at: int
    status: str = TRIAGE_WAITING
    seen_at: Optional[int] = None


@dataclass
class Prescription:
    id: str
    patient_id: str
    doctor_id: str
    drug_code: str
    dose_mg: float
    days: int = 5
    doses_per_day: int = 1
    refills_left: int = 0
    active: bool = True
    created_at: int = 0


@dataclass
class InvoiceLine:
    description: str
    amount_cents: int


@dataclass
class Invoice:
    id: str
    patient_id: str
    appointment_id: str
    lines: List[InvoiceLine] = field(default_factory=list)
    total_cents: int = 0
    paid_cents: int = 0
    status: str = INVOICE_OPEN
    created_at: int = 0
    due_at: int = 0


@dataclass
class Payment:
    id: str
    invoice_id: str
    amount_cents: int
    method: str
    at: int = 0


@dataclass
class Claim:
    id: str
    invoice_id: str
    insurer: str
    covered_cents: int
    status: str = CLAIM_SUBMITTED
    created_at: int = 0


@dataclass
class Message:
    channel: str
    to: str
    body: str
    subject: str = ""
    sent_at: int = 0
