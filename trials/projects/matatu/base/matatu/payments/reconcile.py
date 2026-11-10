"""Applying the provider's statement to the tickets it pays for."""

from dataclasses import dataclass
from typing import Iterable

from ..errors import NotFound
from ..models import TICKET_ISSUED, TICKET_PAID, StatementLine, Ticket
from ..store.repositories import save_ticket
from .matcher import ticket_for_line
from .suspense import add_to_suspense


@dataclass
class ReconcileResult:
    matched: int = 0
    suspended: int = 0
    skipped: int = 0


def _mark_paid(store, ticket: Ticket, line: StatementLine) -> Ticket:
    ticket.status = TICKET_PAID
    ticket.paid_at = line.at
    ticket.payment_code = line.code
    return save_ticket(store, ticket)


def reconcile_statement(store, lines: Iterable[StatementLine], clock) -> ReconcileResult:
    """Goes through a statement line by line. A line already seen is skipped."""
    result = ReconcileResult()
    for line in lines:
        if line.code in store.seen_codes:
            result.skipped += 1
            continue
        store.seen_codes.add(line.code)
        ticket = ticket_for_line(store, line)
        if ticket is None:
            raise NotFound("ticket", line.account_ref)
        if ticket.status != TICKET_ISSUED:
            add_to_suspense(store, line, "ticket not open", clock)
            result.suspended += 1
        elif line.amount_kes != ticket.fare_kes:
            add_to_suspense(store, line, "wrong amount", clock)
            result.suspended += 1
        else:
            _mark_paid(store, ticket, line)
            result.matched += 1
    return result
