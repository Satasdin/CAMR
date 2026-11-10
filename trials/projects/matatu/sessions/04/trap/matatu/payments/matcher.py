"""Working out which ticket a statement line pays for."""

from typing import Optional

from ..models import TICKET_ISSUED, StatementLine, Ticket
from ..store.repositories import tickets_of_phone


def ticket_for_line(store, line: StatementLine) -> Optional[Ticket]:
    ticket = store.tickets.get(line.account_ref)
    if ticket is not None:
        return ticket
    for candidate in tickets_of_phone(store, line.phone):
        if candidate.status == TICKET_ISSUED and candidate.fare_kes == line.amount_kes:
            return candidate
    return None
