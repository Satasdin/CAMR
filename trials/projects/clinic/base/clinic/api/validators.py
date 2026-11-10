"""Checking requests before anything else looks at them."""

from typing import List

from ..errors import ValidationFailed
from ..models import Vitals


def require(request: dict, *keys: str) -> None:
    missing = [key for key in keys if key not in request or request[key] in ("", None)]
    if missing:
        raise ValidationFailed([f"{key} is required" for key in missing])


def check_booking(request: dict) -> None:
    require(request, "patient_id", "doctor_id", "start_at")
    if not isinstance(request["start_at"], int):
        raise ValidationFailed(["start_at must be a whole number of seconds"])


def check_payment(request: dict) -> None:
    require(request, "invoice_id", "amount_cents", "method")
    amount = request["amount_cents"]
    if not isinstance(amount, int) or amount <= 0:
        raise ValidationFailed(["amount_cents must be a positive whole number"])


def vitals_from(request: dict) -> Vitals:
    problems: List[str] = []
    values = {}
    for key, kind in (("temperature_c", float), ("heart_rate", int), ("breaths_per_minute", int), ("systolic", int), ("spo2", int)):
        if key in request:
            try:
                values[key] = kind(request[key])
            except (TypeError, ValueError):
                problems.append(f"{key} is not a number")
    if problems:
        raise ValidationFailed(problems)
    return Vitals(**values)
