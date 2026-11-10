"""Checking requests before they reach the service."""

from typing import Dict, List

from ..errors import ValidationFailed


def missing_fields(request: Dict, fields) -> List[str]:
    return [f"{name} is required" for name in fields if request.get(name) in (None, "")]


def require(request: Dict, *fields) -> None:
    problems = missing_fields(request, fields)
    if problems:
        raise ValidationFailed(problems)


def require_amount(request: Dict, field: str = "amount_cents") -> int:
    require(request, field)
    amount = request[field]
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValidationFailed([f"{field} must be a positive whole number of cents"])
    return amount
