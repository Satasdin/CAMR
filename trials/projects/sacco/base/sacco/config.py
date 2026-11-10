"""Settings shared across the service."""

from dataclasses import dataclass, field
from typing import Dict, Tuple

CURRENCY = "KES"
SHARE_PRICE_CENTS = 20_000
MINIMUM_SHARES = 25
MIN_DEPOSIT_CENTS = 10_000
MIN_SAVINGS_LEFT_CENTS = 100_000
MIN_MEMBERSHIP_MONTHS = 6
MAX_GUARANTORS = 6
GRACE_DAYS = 5
PENALTY_PERCENT = 3
REMINDER_DAYS_BEFORE = 3
DIVIDEND_TAX_PERCENT = 5
ARREARS_REPORT_DAYS = 30
QUIET_HOURS_START = 21
QUIET_HOURS_END = 7
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86_400
DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Settings:
    """Values an installation can override. The defaults suit local development."""

    sender_name: str = "Umoja Sacco"
    support_phone: str = "+254700000000"
    support_email: str = "care@umoja.example"
    notify_channels: Tuple[str, ...] = ("sms", "email")
    statement_footer: str = "Thank you for saving with us."
    labels: Dict[str, str] = field(default_factory=dict)

    def label(self, key: str, default: str = "") -> str:
        return self.labels.get(key, default)


DEFAULT_SETTINGS = Settings()
