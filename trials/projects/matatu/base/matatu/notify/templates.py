"""The words of each message."""

from ..config import DEFAULT_SETTINGS, Settings
from ..models import Ticket
from ..money import format_kes


def ticket_text(ticket: Ticket, settings: Settings = DEFAULT_SETTINGS) -> str:
    return (f"{settings.sender_name}: ticket {ticket.id}, {ticket.from_stage} to {ticket.to_stage}, "
            f"{format_kes(ticket.fare_kes)}. Pay using account {ticket.id}.")


def paid_text(ticket: Ticket, settings: Settings = DEFAULT_SETTINGS) -> str:
    return f"{settings.sender_name}: payment received for ticket {ticket.id}. Safe journey."


def refund_text(ticket: Ticket, settings: Settings = DEFAULT_SETTINGS) -> str:
    return f"{settings.sender_name}: {format_kes(ticket.fare_kes)} returned for ticket {ticket.id}."
