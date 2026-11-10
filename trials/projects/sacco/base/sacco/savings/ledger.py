"""Every movement of money on a savings account."""

from typing import List

from ..errors import NotFound
from ..models import LedgerEntry


def post_entry(store, account_id: str, kind: str, amount_cents: int, clock, reference: str = "", note: str = "") -> LedgerEntry:
    entry = LedgerEntry(id=store.next_id("ENT"), account_id=account_id, kind=kind, amount_cents=amount_cents,
                        at=clock.now(), reference=reference, note=note)
    store.ledger.append(entry)
    return entry


def find_entry(store, entry_id: str) -> LedgerEntry:
    for entry in store.ledger:
        if entry.id == entry_id:
            return entry
    raise NotFound("entry", entry_id)


def entries_for(store, account_id: str) -> List[LedgerEntry]:
    found = [entry for entry in store.ledger if entry.account_id == account_id]
    return sorted(found, key=lambda entry: entry.at)


def balance_of(store, account_id: str) -> int:
    return sum(entry.amount_cents for entry in store.ledger if entry.account_id == account_id)
