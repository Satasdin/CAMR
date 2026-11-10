"""What a borrower owes each month."""

from typing import List

from ..config import DAYS_PER_MONTH, SECONDS_PER_DAY
from ..interest.rates import monthly_interest
from ..models import Instalment, Loan
from ..money import split_evenly


def loan_schedule(loan: Loan) -> List[Instalment]:
    start = loan.disbursed_at or 0
    balance = loan.principal_cents
    instalments = []
    for index, principal in enumerate(split_evenly(loan.principal_cents, loan.term_months), start=1):
        due = start + index * DAYS_PER_MONTH * SECONDS_PER_DAY
        instalments.append(Instalment(index, due, principal, monthly_interest(balance, loan.monthly_rate_bp)))
        balance -= principal
    return instalments


def total_repayable(loan: Loan) -> int:
    return sum(item.total_cents for item in loan_schedule(loan))
