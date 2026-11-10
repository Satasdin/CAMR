"""Collecting a defaulted loan from those who pledged for it."""

from typing import Dict

from ..errors import InvalidLoanState
from ..loans.guarantors import guarantees_for
from ..models import ENTRY_WITHDRAWAL, LOAN_DEFAULTED
from ..money import split_evenly
from ..savings.ledger import post_entry
from ..store.repositories import account_of_member, get_loan


def recover_from_guarantors(store, loan_id: str, clock) -> Dict[str, int]:
    loan = get_loan(store, loan_id)
    if loan.status != LOAN_DEFAULTED:
        raise InvalidLoanState(loan_id, loan.status)
    pledges = guarantees_for(store, loan_id)
    owed = loan.outstanding_principal_cents + loan.accrued_interest_cents + loan.penalty_cents
    taken = {}
    for pledge, share in zip(pledges, split_evenly(owed, len(pledges) or 1)):
        amount = min(share, pledge.amount_cents)
        account = account_of_member(store, pledge.member_id)
        post_entry(store, account.id, ENTRY_WITHDRAWAL, -amount, clock, reference=loan_id, note="guarantor recovery")
        taken[pledge.member_id] = amount
    return taken
