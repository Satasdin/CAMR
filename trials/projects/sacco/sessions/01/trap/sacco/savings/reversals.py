"""Undoing a ledger line posted by mistake."""

from ..errors import AlreadyReversed
from .ledger import balance_of, find_entry


def reverse_entry(store, entry_id: str, reason: str, clock) -> int:
    reversed_entries = getattr(store, "reversed_entries", set())
    if entry_id in reversed_entries:
        raise AlreadyReversed(entry_id)
    entry = find_entry(store, entry_id)
    store.ledger.remove(entry)
    store.reversed_entries = reversed_entries | {entry_id}
    return balance_of(store, entry.account_id)
