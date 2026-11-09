"""Helpers for working with whole cents."""

from typing import Iterable

from .config import CURRENCY


def percent_of(amount_cents: int, percent: int) -> int:
    """Rounds half up, so a share of an amount never comes out a cent short."""
    if amount_cents < 0:
        raise ValueError("amount must not be negative")
    return (amount_cents * percent + 50) // 100


def add(amounts: Iterable[int]) -> int:
    return sum(amounts)


def format_cents(amount_cents: int, currency: str = CURRENCY) -> str:
    sign = "-" if amount_cents < 0 else ""
    whole, part = divmod(abs(amount_cents), 100)
    return f"{sign}{currency} {whole:,}.{part:02d}"


def parse_amount(text: str) -> int:
    """Reads an amount typed by staff, such as '1,250.50', into cents."""
    cleaned = text.replace(",", "").strip()
    if not cleaned:
        raise ValueError("empty amount")
    negative = cleaned.startswith("-")
    if negative:
        cleaned = cleaned[1:]
    whole, _, part = cleaned.partition(".")
    if not whole.isdigit() and whole != "":
        raise ValueError(f"not an amount: {text}")
    if part and (not part.isdigit() or len(part) > 2):
        raise ValueError(f"not an amount: {text}")
    cents = int(whole or "0") * 100 + int((part + "00")[:2] if part else "0")
    return -cents if negative else cents


def split_evenly(amount_cents: int, parts: int) -> list:
    """Splits an amount so the parts always add back to the amount."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    share, remainder = divmod(amount_cents, parts)
    return [share + 1 if index < remainder else share for index in range(parts)]
