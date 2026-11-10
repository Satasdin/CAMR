"""Undoing a ledger line posted by mistake."""

from ..errors import AlreadyReversed
from ..models import ENTRY_REVERSAL
from .ledger import balance_of, find_entry, post_entry


def reverse_entry(store, entry_id: str, reason: str, clock) -> int:
    entry = find_entry(store, entry_id)
    if any(item.kind == ENTRY_REVERSAL and item.reference == entry_id for item in store.ledger):
        raise AlreadyReversed(entry_id)
    post_entry(store, entry.account_id, ENTRY_REVERSAL, -entry.amount_cents, clock, reference=entry.id, note=reason)
    return balance_of(store, entry.account_id)
