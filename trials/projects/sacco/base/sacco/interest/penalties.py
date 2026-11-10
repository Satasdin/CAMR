"""Charges for instalments paid late."""

from typing import Dict

from ..config import PENALTY_PERCENT
from ..models import LOAN_ACTIVE
from ..money import percent_of
from ..repayments.arrears import overdue_cents
from ..store.repositories import save_loan


def penalty_on(overdue: int) -> int:
    return percent_of(overdue, PENALTY_PERCENT)


def charge_penalties(store, now: int) -> Dict[str, int]:
    """Adds a penalty to every active loan with money overdue and returns what was added."""
    charged = {}
    for loan in store.loans.values():
        if loan.status != LOAN_ACTIVE:
            continue
        amount = penalty_on(overdue_cents(store, loan, now))
        if amount:
            loan.penalty_cents += amount
            save_loan(store, loan)
            charged[loan.id] = amount
    return charged
