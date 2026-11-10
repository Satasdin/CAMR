"""Working out which ticket a statement line pays for."""

from typing import Optional

from ..models import StatementLine, Ticket


def _plain(reference: str) -> str:
    return "".join(character for character in reference.upper() if character.isalnum())


def ticket_for_line(store, line: StatementLine) -> Optional[Ticket]:
    wanted = _plain(line.account_ref)
    if not wanted:
        return None
    for ticket in store.tickets.values():
        if _plain(ticket.id) == wanted:
            return ticket
    return None
