"""Settings shared across the service."""

from dataclasses import dataclass, field
from typing import Dict, Tuple

CURRENCY = "KES"
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86_400

CLINIC_OPEN_HOUR = 8
CLINIC_CLOSE_HOUR = 17
SLOT_MINUTES = 20
MAX_ADVANCE_BOOKING_DAYS = 56
CANCEL_NOTICE_HOURS = 24
LATE_CANCEL_FEE_CENTS = 50_000
WAITLIST_OFFER_HOURS = 6

REMINDER_WINDOW_HOURS = 24
INVOICE_DUE_DAYS = 30
MAX_REFILLS = 5
SMALL_BALANCE_CENTS = 20_000
MIN_NAME_LENGTH = 2

DEPARTMENTS: Tuple[str, ...] = ("General Medicine", "Cardiology", "Oncology", "Paediatrics", "Dermatology")


@dataclass(frozen=True)
class Insurer:
    code: str
    label: str
    cover_percent: int


INSURERS: Dict[str, Insurer] = {
    "tumaini": Insurer("tumaini", "Tumaini Health", 80),
    "baraka": Insurer("baraka", "Baraka Mutual", 70),
    "uzima": Insurer("uzima", "Uzima Cover", 100),
}


@dataclass(frozen=True)
class Settings:
    """Values an installation can override. The defaults suit local development."""

    clinic_name: str = "Mawingu Clinic"
    front_desk_phone: str = "+254700000100"
    accounts_phone: str = "+254700000101"
    support_email: str = "frontdesk@mawingu.example"
    labels: Dict[str, str] = field(default_factory=dict)

    def label(self, key: str, default: str = "") -> str:
        return self.labels.get(key, default)


DEFAULT_SETTINGS = Settings()


def insurer(code: str) -> Insurer:
    try:
        return INSURERS[code]
    except KeyError:
        raise ValueError(f"unknown insurer: {code}") from None
