"""Turning monthly rates into amounts."""

from ..money import basis_points_of


def monthly_interest(balance_cents: int, monthly_rate_bp: int) -> int:
    return basis_points_of(balance_cents, monthly_rate_bp)


def yearly_percent(monthly_rate_bp: int) -> float:
    return monthly_rate_bp * 12 / 100
