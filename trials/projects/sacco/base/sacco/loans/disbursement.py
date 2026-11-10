"""Sending an approved loan to the member."""

from ..errors import InvalidLoanState
from ..models import LOAN_ACTIVE, LOAN_APPROVED, Disbursement, Loan
from ..store.repositories import get_loan, get_member, save_loan


def _activate(store, loan: Loan, clock) -> Loan:
    loan.status = LOAN_ACTIVE
    loan.disbursed_at = clock.now()
    loan.outstanding_principal_cents = loan.principal_cents
    return save_loan(store, loan)


def disburse_loan(store, loan_id: str, gateway, clock) -> Disbursement:
    loan = get_loan(store, loan_id)
    if loan.status != LOAN_APPROVED:
        raise InvalidLoanState(loan_id, loan.status)
    member = get_member(store, loan.member_id)
    transfer = gateway.send(member.phone, loan.principal_cents, reference=loan.id)
    _activate(store, loan, clock)
    return Disbursement(loan.id, sent_cents=loan.principal_cents, receipt_id=transfer.transfer_id)
