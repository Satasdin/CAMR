"""Applying for a loan and deciding on it."""

from ..errors import InvalidLoanState, NotSecured, ValidationFailed
from ..models import LOAN_APPLIED, LOAN_APPROVED, LOAN_REJECTED, Loan
from ..store.repositories import get_loan, get_member, save_loan
from .eligibility import application_problems
from .guarantors import security_gap
from .products import product


def apply_for_loan(store, member_id: str, product_code: str, amount_cents: int, term_months: int, clock) -> Loan:
    member = get_member(store, member_id)
    loan_product = product(product_code)
    problems = application_problems(store, member, loan_product, amount_cents, term_months, clock.now())
    if problems:
        raise ValidationFailed(problems)
    loan = Loan(id=store.next_id("LN"), member_id=member_id, product=loan_product.code, principal_cents=amount_cents,
                term_months=term_months, monthly_rate_bp=loan_product.monthly_rate_bp, applied_at=clock.now())
    return save_loan(store, loan)


def approve_loan(store, loan_id: str, clock) -> Loan:
    loan = get_loan(store, loan_id)
    if loan.status != LOAN_APPLIED:
        raise InvalidLoanState(loan_id, loan.status)
    short_by = security_gap(store, loan)
    if short_by:
        raise NotSecured(loan_id, short_by)
    loan.status = LOAN_APPROVED
    loan.approved_at = clock.now()
    return save_loan(store, loan)


def reject_loan(store, loan_id: str, reason: str) -> Loan:
    loan = get_loan(store, loan_id)
    if loan.status != LOAN_APPLIED:
        raise InvalidLoanState(loan_id, loan.status)
    loan.status = LOAN_REJECTED
    loan.rejection_reason = reason
    return save_loan(store, loan)
