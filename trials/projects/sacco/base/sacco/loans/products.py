"""The loans the co-operative offers."""

from dataclasses import dataclass
from typing import Dict

from ..errors import ValidationFailed


@dataclass(frozen=True)
class LoanProduct:
    code: str
    label: str
    monthly_rate_bp: int
    max_term_months: int
    savings_multiple: int


PRODUCTS: Dict[str, LoanProduct] = {
    "normal": LoanProduct("normal", "Normal", 100, 36, 3),
    "emergency": LoanProduct("emergency", "Emergency", 150, 12, 1),
    "development": LoanProduct("development", "Development", 120, 48, 4),
}


def product(code: str) -> LoanProduct:
    try:
        return PRODUCTS[code]
    except KeyError:
        raise ValidationFailed([f"unknown loan product: {code}"]) from None
