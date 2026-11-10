"""Checking a passenger on to the vehicle."""

from ..errors import TicketNotValid
from ..models import TICKET_PAID, Ticket
from ..store.repositories import get_ticket, save_ticket


def board_ticket(store, ticket_id: str, trip_id: str, clock) -> Ticket:
    ticket = get_ticket(store, ticket_id)
    if ticket.trip_id != trip_id:
        raise TicketNotValid(ticket_id, "for a different trip")
    if ticket.status != TICKET_PAID:
        raise TicketNotValid(ticket_id, f"status is {ticket.status}")
    if ticket.boarded_at is not None:
        raise TicketNotValid(ticket_id, "already boarded")
    ticket.boarded_at = clock.now()
    return save_ticket(store, ticket)


def on_board(store, trip_id: str) -> list:
    return [ticket for ticket in store.tickets.values() if ticket.trip_id == trip_id and ticket.boarded_at is not None]
