"""Charging each active loan its month of interest."""

from typing import Dict

from ..models import LOAN_ACTIVE
from ..store.repositories import save_loan
from .rates import monthly_interest


def accrue_month(store) -> Dict[str, int]:
    """Adds one month of interest to every active loan and returns what was added."""
    charged = {}
    for loan in store.loans.values():
        if loan.status != LOAN_ACTIVE:
            continue
        amount = monthly_interest(loan.outstanding_principal_cents, loan.monthly_rate_bp)
        loan.accrued_interest_cents += amount
        save_loan(store, loan)
        charged[loan.id] = amount
    return charged
