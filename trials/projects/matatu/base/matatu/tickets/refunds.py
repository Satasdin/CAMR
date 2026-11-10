"""Giving money back for tickets that were not used."""

from ..config import REFUND_WINDOW_SECONDS
from ..errors import RefundRefused
from ..models import METHOD_MOBILE, TICKET_PAID, TICKET_REFUNDED, Refund, Ticket
from ..store.repositories import get_ticket, save_refund, save_ticket


def refund_ticket(store, ticket_id: str, provider, clock, reason: str = "") -> Ticket:
    ticket = get_ticket(store, ticket_id)
    if ticket.status != TICKET_PAID:
        raise RefundRefused(ticket_id, f"status is {ticket.status}")
    if ticket.boarded_at is not None:
        raise RefundRefused(ticket_id, "already boarded")
    now = clock.now()
    if now - (ticket.paid_at or 0) > REFUND_WINDOW_SECONDS:
        raise RefundRefused(ticket_id, "too late")
    if ticket.method == METHOD_MOBILE:
        provider.send_back(ticket.phone, ticket.fare_kes, ticket.id)
    ticket.status = TICKET_REFUNDED
    save_refund(store, Refund(id=store.next_id("RFD"), ticket_id=ticket_id, amount_kes=ticket.fare_kes,
                              reason=reason, created_at=now))
    return save_ticket(store, ticket)
