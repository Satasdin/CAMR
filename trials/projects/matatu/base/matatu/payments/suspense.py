"""Statement lines that need a person to look at them."""

from typing import List

from ..models import StatementLine, SuspenseItem


def add_to_suspense(store, line: StatementLine, reason: str, clock) -> SuspenseItem:
    item = SuspenseItem(line_code=line.code, reason=reason, phone=line.phone, amount_kes=line.amount_kes,
                        account_ref=line.account_ref, created_at=clock.now())
    store.suspense.append(item)
    return item


def pending_suspense(store) -> List[SuspenseItem]:
    return [item for item in store.suspense if not item.resolved]


def resolve_suspense(item: SuspenseItem, resolution: str) -> SuspenseItem:
    item.resolved = True
    item.resolution = resolution
    return item
