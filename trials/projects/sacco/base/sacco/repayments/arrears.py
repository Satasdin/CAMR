"""Working out how far behind a borrower is."""

from ..config import GRACE_DAYS, SECONDS_PER_DAY
from ..loans.schedule import loan_schedule
from ..models import Loan
from ..store.repositories import repayments_for


def paid_towards_schedule(store, loan_id: str) -> int:
    return sum(item.amount_cents for item in repayments_for(store, loan_id))


def overdue_cents(store, loan: Loan, now: int) -> int:
    cutoff = now - GRACE_DAYS * SECONDS_PER_DAY
    due = sum(item.total_cents for item in loan_schedule(loan) if item.due_at <= cutoff)
    return max(0, due - paid_towards_schedule(store, loan.id))


def days_in_arrears(store, loan: Loan, now: int) -> int:
    paid = paid_towards_schedule(store, loan.id)
    for item in loan_schedule(loan):
        if paid >= item.total_cents:
            paid -= item.total_cents
            continue
        return max(0, (now - item.due_at) // SECONDS_PER_DAY)
    return 0
