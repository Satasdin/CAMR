"""A borrower's position on one loan."""

from typing import Dict

from ..loans.schedule import loan_schedule
from ..store.repositories import get_loan, repayments_for


def loan_statement(store, loan_id: str) -> Dict:
    loan = get_loan(store, loan_id)
    return {
        "loan_id": loan.id,
        "status": loan.status,
        "principal_cents": loan.principal_cents,
        "outstanding_principal_cents": loan.outstanding_principal_cents,
        "accrued_interest_cents": loan.accrued_interest_cents,
        "penalty_cents": loan.penalty_cents,
        "repayments": [{"id": item.id, "at": item.at, "amount_cents": item.amount_cents} for item in repayments_for(store, loan_id)],
        "schedule": [{"number": item.number, "due_at": item.due_at, "total_cents": item.total_cents} for item in loan_schedule(loan)],
    }
