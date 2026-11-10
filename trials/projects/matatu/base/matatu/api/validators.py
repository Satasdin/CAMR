"""Checking requests before they reach the back office."""

from typing import Dict, List

from ..config import RIDER_TYPES
from ..errors import ValidationFailed

REQUIRED_SALE_FIELDS = ("trip_id", "from_stage", "to_stage", "phone")


def missing_fields(request: Dict, fields) -> List[str]:
    return [f"{name} is required" for name in fields if request.get(name) in (None, "")]


def phone_problems(phone: str) -> List[str]:
    if not phone.startswith("+254") or not phone[1:].isdigit() or len(phone) != 13:
        return ["phone must look like +254700000000"]
    return []


def sale_problems(request: Dict) -> List[str]:
    problems = missing_fields(request, REQUIRED_SALE_FIELDS)
    if problems:
        return problems
    problems.extend(phone_problems(request["phone"]))
    if request.get("rider", "adult") not in RIDER_TYPES:
        problems.append("rider is not one we know")
    bags = request.get("bags", 0)
    if not isinstance(bags, int) or isinstance(bags, bool) or bags < 0:
        problems.append("bags must be a whole number")
    return problems


def require(request: Dict, *fields) -> None:
    problems = missing_fields(request, fields)
    if problems:
        raise ValidationFailed(problems)


def check_sale(request: Dict) -> None:
    problems = sale_problems(request)
    if problems:
        raise ValidationFailed(problems)
