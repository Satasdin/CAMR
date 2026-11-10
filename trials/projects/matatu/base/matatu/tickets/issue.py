"""Selling a ticket for a seat on a trip."""

from ..config import DEFAULT_SETTINGS, MAX_TICKETS_PER_PHONE, RIDER_ADULT, Settings
from ..errors import NoSeatsLeft, TooManyTickets, TripNotOpen
from ..fares.quote import quote_fare
from ..models import METHOD_CASH, METHOD_MOBILE, TICKET_CANCELLED, TICKET_PAID, TRIP_SCHEDULED, Ticket
from ..routes.network import stages_between
from ..store.repositories import get_route, get_trip, get_vehicle, save_ticket, tickets_on_trip


def _live(tickets) -> list:
    return [ticket for ticket in tickets if ticket.status != TICKET_CANCELLED]


def issue_ticket(store, trip_id: str, from_stage: str, to_stage: str, phone: str, clock, method: str = METHOD_MOBILE,
                 rider: str = RIDER_ADULT, bags: int = 0, raining: bool = False,
                 settings: Settings = DEFAULT_SETTINGS) -> Ticket:
    """Sells one seat. Cash tickets are paid at once; mobile tickets wait for the statement."""
    trip = get_trip(store, trip_id)
    if trip.status != TRIP_SCHEDULED:
        raise TripNotOpen(trip_id, trip.status)
    sold = _live(tickets_on_trip(store, trip_id))
    if len(sold) >= get_vehicle(store, trip.vehicle_id).seats:
        raise NoSeatsLeft(trip_id)
    if sum(1 for ticket in sold if ticket.phone == phone) >= MAX_TICKETS_PER_PHONE:
        raise TooManyTickets(phone, MAX_TICKETS_PER_PHONE)
    route = get_route(store, trip.route_id)
    now = clock.now()
    quote = quote_fare(stages_between(route, from_stage, to_stage), now, rider, bags, raining, settings)
    ticket = Ticket(id=store.next_id("TKT"), trip_id=trip_id, route_id=route.id, vehicle_id=trip.vehicle_id,
                    from_stage=from_stage, to_stage=to_stage, phone=phone, fare_kes=quote.total_kes, method=method,
                    issued_at=now)
    if method == METHOD_CASH:
        ticket.status = TICKET_PAID
        ticket.paid_at = now
    return save_ticket(store, ticket)


def cancel_ticket(store, ticket: Ticket) -> Ticket:
    ticket.status = TICKET_CANCELLED
    return save_ticket(store, ticket)
