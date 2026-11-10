"""What crews earn from the fares they carry."""

from ..config import COMMISSION_EXCLUDED_ROUTES, CONDUCTOR_COMMISSION_PERCENT, DRIVER_COMMISSION_PERCENT, ROLE_DRIVER
from ..models import TICKET_PAID, CrewMember, Shift, Ticket
from ..money import percent_of
from ..store.repositories import get_crew_member


def rate_for(member: CrewMember) -> int:
    return DRIVER_COMMISSION_PERCENT if member.role == ROLE_DRIVER else CONDUCTOR_COMMISSION_PERCENT


def commission_on(ticket: Ticket, member: CrewMember) -> int:
    if ticket.route_id in COMMISSION_EXCLUDED_ROUTES:
        return 0
    return percent_of(ticket.fare_kes, rate_for(member))


def _in_shift(ticket: Ticket, shift: Shift) -> bool:
    if ticket.vehicle_id != shift.vehicle_id or ticket.status != TICKET_PAID:
        return False
    return ticket.issued_at >= shift.started_at and (shift.ended_at is None or ticket.issued_at <= shift.ended_at)


def commission_for_shift(store, shift: Shift) -> int:
    member = get_crew_member(store, shift.crew_id)
    return sum(commission_on(ticket, member) for ticket in store.tickets.values() if _in_shift(ticket, shift))
