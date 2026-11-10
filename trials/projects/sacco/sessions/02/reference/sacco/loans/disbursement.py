"""Sending an approved loan to the member."""

from ..errors import InvalidLoanState
from ..models import LOAN_ACTIVE, LOAN_APPROVED, Disbursement, Loan
from ..money import basis_points_of
from ..store.repositories import get_loan, get_member, save_loan
from .fees import record_fee_income

PROCESSING_FEE_BASIS_POINTS = 150


def processing_fee(amount_cents: int) -> int:
    return basis_points_of(amount_cents, PROCESSING_FEE_BASIS_POINTS)


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
    fee = processing_fee(loan.principal_cents)
    sent = loan.principal_cents - fee
    transfer = gateway.send(member.phone, sent, reference=loan.id)
    _activate(store, loan, clock)
    record_fee_income(store, loan.id, fee, clock)
    return Disbursement(loan.id, sent_cents=sent, fee_cents=fee, receipt_id=transfer.transfer_id)
