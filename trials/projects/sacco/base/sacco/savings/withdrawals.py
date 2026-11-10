"""Money leaving a savings account."""

from ..config import MIN_SAVINGS_LEFT_CENTS
from ..errors import InsufficientSavings, MemberInactive, ValidationFailed
from ..loans.guarantors import pledged_by
from ..models import ENTRY_WITHDRAWAL, LedgerEntry
from ..store.repositories import account_of_member, get_member
from .accounts import savings_balance
from .ledger import post_entry


def available_to_withdraw(store, member_id: str) -> int:
    balance = savings_balance(store, member_id)
    return max(0, balance - pledged_by(store, member_id) - MIN_SAVINGS_LEFT_CENTS)


def withdraw(store, member_id: str, amount_cents: int, clock, reference: str = "") -> LedgerEntry:
    if amount_cents <= 0:
        raise ValidationFailed(["amount must be positive"])
    member = get_member(store, member_id)
    if not member.active:
        raise MemberInactive(member_id)
    available = available_to_withdraw(store, member_id)
    if amount_cents > available:
        raise InsufficientSavings(amount_cents, available)
    account = account_of_member(store, member_id)
    return post_entry(store, account.id, ENTRY_WITHDRAWAL, -amount_cents, clock, reference=reference)
