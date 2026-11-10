"""Helpers for working with whole shillings."""

from typing import Iterable

from .config import CURRENCY


def percent_of(amount_kes: int, percent: int) -> int:
    """Rounds half up."""
    if amount_kes < 0:
        raise ValueError("amount must not be negative")
    return (amount_kes * percent + 50) // 100


def add(amounts: Iterable[int]) -> int:
    return sum(amounts)


def round_up_to(amount_kes: int, step: int) -> int:
    if step <= 0:
        raise ValueError("step must be positive")
    return -(-amount_kes // step) * step


def format_kes(amount_kes: int, currency: str = CURRENCY) -> str:
    sign = "-" if amount_kes < 0 else ""
    return f"{sign}{currency} {abs(amount_kes):,}"


def parse_amount(text: str) -> int:
    """Reads an amount from a statement or typed by staff, such as '1,250' or '1,250.00'."""
    cleaned = text.replace(",", "").strip()
    if not cleaned:
        raise ValueError("empty amount")
    whole, _, part = cleaned.partition(".")
    if not whole.isdigit():
        raise ValueError(f"not an amount: {text}")
    if part.strip("0"):
        raise ValueError(f"not a whole number of shillings: {text}")
    return int(whole)


def split_evenly(amount_kes: int, parts: int) -> list:
    """Splits an amount so the parts always add back to the amount."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    share, remainder = divmod(amount_kes, parts)
    return [share + 1 if index < remainder else share for index in range(parts)]
