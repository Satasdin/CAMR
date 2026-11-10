"""Splitting a payment between what a borrower owes."""

from dataclasses import dataclass

from ..models import Loan


@dataclass
class Allocation:
    penalty_cents: int
    interest_cents: int
    principal_cents: int
    excess_cents: int


def allocate(loan: Loan, amount_cents: int) -> Allocation:
    remaining = amount_cents
    penalty = min(remaining, loan.penalty_cents)
    remaining -= penalty
    interest = min(remaining, loan.accrued_interest_cents)
    remaining -= interest
    principal = min(remaining, loan.outstanding_principal_cents)
    remaining -= principal
    return Allocation(penalty, interest, principal, remaining)
