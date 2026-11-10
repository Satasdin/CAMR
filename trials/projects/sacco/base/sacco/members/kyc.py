"""Checking who a member is before they join."""

from typing import List


def normalise_phone(phone: str) -> str:
    """Turns local numbers such as 0712345678 into +254712345678."""
    cleaned = phone.replace(" ", "").replace("-", "")
    if cleaned.startswith("07") or cleaned.startswith("01"):
        return "+254" + cleaned[1:]
    if cleaned.startswith("254"):
        return "+" + cleaned
    return cleaned


def phone_problems(phone: str) -> List[str]:
    cleaned = normalise_phone(phone)
    if not cleaned.startswith("+254") or len(cleaned) != 13 or not cleaned[1:].isdigit():
        return [f"{phone} is not a Kenyan mobile number"]
    return []


def national_id_problems(national_id: str) -> List[str]:
    if not national_id.isdigit() or not 7 <= len(national_id) <= 8:
        return ["national_id must be 7 or 8 digits"]
    return []


def member_problems(name: str, phone: str, national_id: str) -> List[str]:
    problems = [] if name.strip() else ["name is required"]
    return problems + phone_problems(phone) + national_id_problems(national_id)
