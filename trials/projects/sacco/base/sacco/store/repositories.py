"""Small helpers for reading and writing records in a store."""

from typing import List

from ..errors import NotFound
from ..models import Loan, Member, SavingsAccount


def save_member(store, member: Member) -> Member:
    store.members[member.id] = member
    return member


def get_member(store, member_id: str) -> Member:
    try:
        return store.members[member_id]
    except KeyError:
        raise NotFound("member", member_id) from None


def save_account(store, account: SavingsAccount) -> SavingsAccount:
    store.accounts[account.id] = account
    return account


def get_account(store, account_id: str) -> SavingsAccount:
    try:
        return store.accounts[account_id]
    except KeyError:
        raise NotFound("account", account_id) from None


def account_of_member(store, member_id: str) -> SavingsAccount:
    for account in store.accounts.values():
        if account.member_id == member_id:
            return account
    raise NotFound("account for member", member_id)


def save_loan(store, loan: Loan) -> Loan:
    store.loans[loan.id] = loan
    return loan


def get_loan(store, loan_id: str) -> Loan:
    try:
        return store.loans[loan_id]
    except KeyError:
        raise NotFound("loan", loan_id) from None


def loans_of(store, member_id: str) -> List[Loan]:
    return [loan for loan in store.loans.values() if loan.member_id == member_id]


def repayments_for(store, loan_id: str) -> list:
    return [item for item in store.repayments if item.loan_id == loan_id]
