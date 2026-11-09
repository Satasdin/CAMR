"""Checking requests before they reach the service."""

from typing import Dict, List

from ..config import MAX_WEIGHT_KG, MIN_WEIGHT_KG, SERVICE_LEVELS
from ..errors import ValidationFailed
from ..pricing.zones import is_known

REQUIRED_PARCEL_FIELDS = ("customer_id", "origin_zone", "destination_zone", "weight_kg")


def missing_fields(request: Dict, fields) -> List[str]:
    return [f"{name} is required" for name in fields if request.get(name) in (None, "")]


def parcel_problems(request: Dict) -> List[str]:
    problems = missing_fields(request, REQUIRED_PARCEL_FIELDS)
    if problems:
        return problems
    for key in ("origin_zone", "destination_zone"):
        if not is_known(request[key]):
            problems.append(f"{key} is not a zone we serve")
    weight = request["weight_kg"]
    if not isinstance(weight, (int, float)) or isinstance(weight, bool):
        problems.append("weight_kg must be a number")
    elif not MIN_WEIGHT_KG <= weight <= MAX_WEIGHT_KG:
        problems.append(f"weight_kg must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG}")
    if request.get("service", "standard") not in SERVICE_LEVELS:
        problems.append("service is not one we offer")
    return problems


def require(request: Dict, *fields) -> None:
    problems = missing_fields(request, fields)
    if problems:
        raise ValidationFailed(problems)


def check_parcel(request: Dict) -> None:
    problems = parcel_problems(request)
    if problems:
        raise ValidationFailed(problems)
