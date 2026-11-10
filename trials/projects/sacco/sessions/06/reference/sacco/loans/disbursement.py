"""Sending an approved loan to the member."""

from ..errors import InvalidLoanState
from ..models import ENTRY_FEE, LOAN_ACTIVE, LOAN_APPROVED, Disbursement, Loan
from ..money import basis_points_of
from ..savings.ledger import post_entry
from ..store.repositories import account_of_member, get_loan, get_member, save_loan
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
    transfer = gateway.send(member.phone, loan.principal_cents, reference=loan.id)
    _activate(store, loan, clock)
    account = account_of_member(store, loan.member_id)
    post_entry(store, account.id, ENTRY_FEE, -fee, clock, reference=loan.id, note="processing fee")
    record_fee_income(store, loan.id, fee, clock)
    return Disbursement(loan.id, sent_cents=loan.principal_cents, fee_cents=fee, receipt_id=transfer.transfer_id)
