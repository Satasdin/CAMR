"""Opening and reading savings accounts."""

from ..models import SavingsAccount
from ..store.repositories import account_of_member, save_account
from .ledger import balance_of


def open_account(store, member_id: str, clock) -> SavingsAccount:
    account = SavingsAccount(id=store.next_id("SAV"), member_id=member_id, created_at=clock.now())
    return save_account(store, account)


def savings_balance(store, member_id: str) -> int:
    return balance_of(store, account_of_member(store, member_id).id)


def freeze_account(store, member_id: str) -> SavingsAccount:
    account = account_of_member(store, member_id)
    account.frozen = True
    return save_account(store, account)
