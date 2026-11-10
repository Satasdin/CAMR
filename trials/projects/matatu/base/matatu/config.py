"""Settings shared across the back office."""

from dataclasses import dataclass, field
from typing import Dict, Tuple

CURRENCY = "KES"
LOCAL_OFFSET_HOURS = 3
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86_400

MIN_FARE_KES = 30
MAX_FARE_KES = 300
FARE_ROUNDING_KES = 10
MAX_TICKETS_PER_PHONE = 6
REFUND_WINDOW_SECONDS = 900
INSPECTION_INTERVAL_DAYS = 120
SACCO_LEVY_PERCENT = 8
DRIVER_COMMISSION_PERCENT = 12
CONDUCTOR_COMMISSION_PERCENT = 8
COMMISSION_EXCLUDED_ROUTES = ("33B",)
DAY_PASS_PRICE_KES = 350

ROLE_DRIVER = "driver"
ROLE_CONDUCTOR = "conductor"

RIDER_ADULT = "adult"
RIDER_STUDENT = "student"
RIDER_CHILD = "child"
RIDER_TYPES = (RIDER_ADULT, RIDER_STUDENT, RIDER_CHILD)


@dataclass(frozen=True)
class FareBand:
    code: str
    max_stages: int
    fare_kes: int


FARE_BANDS: Tuple[FareBand, ...] = (
    FareBand("short", 3, 50),
    FareBand("medium", 7, 80),
    FareBand("long", 99, 120),
)


@dataclass(frozen=True)
class Settings:
    """Values an installation can override. The defaults suit local development."""

    sender_name: str = "Matatu"
    support_phone: str = "+254700000000"
    peak_percent: int = 125
    rain_extra_kes: int = 20
    student_discount_percent: int = 20
    child_discount_percent: int = 50
    labels: Dict[str, str] = field(default_factory=dict)

    def label(self, key: str, default: str = "") -> str:
        return self.labels.get(key, default)


DEFAULT_SETTINGS = Settings()
