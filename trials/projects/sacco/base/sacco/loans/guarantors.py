"""Members who stand behind another member's loan."""

from typing import List

from ..config import MAX_GUARANTORS
from ..errors import ValidationFailed
from ..models import Guarantee, Loan
from ..savings.accounts import savings_balance
from ..store.repositories import get_loan, get_member


def guarantees_for(store, loan_id: str) -> List[Guarantee]:
    return [item for item in store.guarantees if item.loan_id == loan_id and not item.released]


def pledged_by(store, member_id: str) -> int:
    return sum(item.amount_cents for item in store.guarantees if item.member_id == member_id and not item.released)


def add_guarantee(store, loan_id: str, member_id: str, amount_cents: int, clock) -> Guarantee:
    loan = get_loan(store, loan_id)
    get_member(store, member_id)
    if member_id == loan.member_id:
        raise ValidationFailed(["a member cannot guarantee their own loan"])
    if len(guarantees_for(store, loan_id)) >= MAX_GUARANTORS:
        raise ValidationFailed([f"a loan can have at most {MAX_GUARANTORS} guarantors"])
    if amount_cents <= 0 or amount_cents > savings_balance(store, member_id) - pledged_by(store, member_id):
        raise ValidationFailed(["pledge is more than the guarantor has free"])
    guarantee = Guarantee(loan_id=loan_id, member_id=member_id, amount_cents=amount_cents, created_at=clock.now())
    store.guarantees.append(guarantee)
    return guarantee


def security_gap(store, loan: Loan) -> int:
    """How much of the loan is still not covered by savings and pledges."""
    pledged = sum(item.amount_cents for item in guarantees_for(store, loan.id))
    covered = savings_balance(store, loan.member_id) + pledged
    return max(0, loan.principal_cents - covered)


def release_guarantees(store, loan_id: str) -> int:
    released = guarantees_for(store, loan_id)
    for item in released:
        item.released = True
    return len(released)
