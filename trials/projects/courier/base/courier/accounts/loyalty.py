"""Points customers earn and spend."""

from dataclasses import dataclass
from typing import List

from ..errors import ValidationFailed
from ..store.repositories import get_customer, save_customer

POINTS_PER_100_SHILLINGS = 1
REDEEM_CENTS_PER_POINT = 50
MINIMUM_REDEMPTION = 100
TIER_NAMES = ((5_000, "Gold"), (2_000, "Silver"), (500, "Bronze"))


@dataclass
class PointsChange:
    customer_id: str
    change: int
    balance: int
    reason: str


def points_earned(paid_cents: int) -> int:
    return paid_cents // 10_000 * POINTS_PER_100_SHILLINGS


def tier_of(points: int) -> str:
    for threshold, name in TIER_NAMES:
        if points >= threshold:
            return name
    return "Member"


def add_points(store, customer_id: str, paid_cents: int) -> PointsChange:
    customer = get_customer(store, customer_id)
    earned = points_earned(paid_cents)
    customer.loyalty_points += earned
    save_customer(store, customer)
    return PointsChange(customer_id, earned, customer.loyalty_points, "payment")


def redeem_points(store, customer_id: str, points: int) -> int:
    """Spends points and returns what they are worth in cents."""
    customer = get_customer(store, customer_id)
    problems: List[str] = []
    if points < MINIMUM_REDEMPTION:
        problems.append(f"at least {MINIMUM_REDEMPTION} points must be redeemed")
    if points > customer.loyalty_points:
        problems.append("not enough points")
    if problems:
        raise ValidationFailed(problems)
    customer.loyalty_points -= points
    save_customer(store, customer)
    return points * REDEEM_CENTS_PER_POINT
