"""Money coming into a savings account."""

from ..config import MIN_DEPOSIT_CENTS
from ..errors import MemberInactive, ValidationFailed
from ..models import ENTRY_DEPOSIT, LedgerEntry
from ..money import format_cents
from ..store.repositories import account_of_member, get_member
from .ledger import post_entry


def deposit(store, member_id: str, amount_cents: int, clock, source: str = "branch", reference: str = "") -> LedgerEntry:
    if amount_cents < MIN_DEPOSIT_CENTS:
        raise ValidationFailed([f"deposits start at {format_cents(MIN_DEPOSIT_CENTS)}"])
    member = get_member(store, member_id)
    if not member.active:
        raise MemberInactive(member_id)
    account = account_of_member(store, member_id)
    if account.frozen:
        raise ValidationFailed(["this account is frozen"])
    return post_entry(store, account.id, ENTRY_DEPOSIT, amount_cents, clock, reference=reference, note=source)
