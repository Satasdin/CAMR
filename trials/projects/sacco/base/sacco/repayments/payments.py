"""Applying a payment to a loan."""

from ..errors import InvalidLoanState, ValidationFailed
from ..loans.guarantors import release_guarantees
from ..models import ENTRY_DEPOSIT, LOAN_ACTIVE, LOAN_CLEARED, Repayment
from ..savings.ledger import post_entry
from ..store.repositories import account_of_member, get_loan, save_loan
from .allocation import allocate


def apply_repayment(store, loan_id: str, amount_cents: int, clock, source: str = "branch", reference: str = "") -> Repayment:
    if amount_cents <= 0:
        raise ValidationFailed(["amount must be positive"])
    loan = get_loan(store, loan_id)
    if loan.status != LOAN_ACTIVE:
        raise InvalidLoanState(loan_id, loan.status)
    split = allocate(loan, amount_cents)
    loan.penalty_cents -= split.penalty_cents
    loan.accrued_interest_cents -= split.interest_cents
    loan.outstanding_principal_cents -= split.principal_cents
    repayment = Repayment(id=store.next_id("RPY"), loan_id=loan.id, amount_cents=amount_cents, at=clock.now(),
                          penalty_cents=split.penalty_cents, interest_cents=split.interest_cents,
                          principal_cents=split.principal_cents, source=source, reference=reference)
    store.repayments.append(repayment)
    if split.excess_cents:
        account = account_of_member(store, loan.member_id)
        post_entry(store, account.id, ENTRY_DEPOSIT, split.excess_cents, clock, reference=loan.id, note="overpayment")
    if loan.outstanding_principal_cents == 0 and loan.accrued_interest_cents == 0 and loan.penalty_cents == 0:
        loan.status = LOAN_CLEARED
        loan.cleared_at = clock.now()
        release_guarantees(store, loan.id)
    save_loan(store, loan)
    return repayment
