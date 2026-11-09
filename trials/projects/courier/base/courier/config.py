"""Settings shared across the service."""

from dataclasses import dataclass, field
from typing import Dict, Tuple

CURRENCY = "KES"
MAX_WEIGHT_KG = 30
MIN_WEIGHT_KG = 0.1
VOLUMETRIC_DIVISOR = 5000
INVOICE_DUE_DAYS = 14
REFUND_REVIEW_LIMIT_CENTS = 500_000
QUIET_HOURS_START = 21
QUIET_HOURS_END = 7
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class ServiceLevel:
    code: str
    label: str
    multiplier_percent: int
    transit_days: int


SERVICE_LEVELS: Dict[str, ServiceLevel] = {
    "standard": ServiceLevel("standard", "Standard", 100, 3),
    "express": ServiceLevel("express", "Express", 160, 1),
    "economy": ServiceLevel("economy", "Economy", 80, 5),
}


@dataclass(frozen=True)
class Settings:
    """Values an installation can override. The defaults suit local development."""

    sender_name: str = "Courier"
    support_phone: str = "+254700000000"
    support_email: str = "support@courier.example"
    notify_channels: Tuple[str, ...] = ("sms", "email")
    fuel_percent: int = 7
    remote_area_cents: int = 45_000
    insurance_percent: int = 2
    labels: Dict[str, str] = field(default_factory=dict)

    def label(self, key: str, default: str = "") -> str:
        return self.labels.get(key, default)


DEFAULT_SETTINGS = Settings()


def service_level(code: str) -> ServiceLevel:
    try:
        return SERVICE_LEVELS[code]
    except KeyError:
        raise ValueError(f"unknown service level: {code}") from None
