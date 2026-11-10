"""Working out which ticket a statement line pays for."""

from typing import Optional

from ..models import StatementLine, Ticket


def ticket_for_line(store, line: StatementLine) -> Optional[Ticket]:
    return store.tickets.get(line.account_ref)
