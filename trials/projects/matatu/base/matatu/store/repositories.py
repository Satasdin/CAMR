"""Small helpers for reading and writing records in a store."""

from typing import List

from ..errors import NotFound
from ..models import CrewMember, DayPass, Owner, Refund, Route, Shift, Stage, Ticket, Trip, Vehicle


def _get(table, kind: str, identifier: str):
    try:
        return table[identifier]
    except KeyError:
        raise NotFound(kind, identifier) from None


def save_stage(store, stage: Stage) -> Stage:
    store.stages[stage.id] = stage
    return stage


def get_stage(store, stage_id: str) -> Stage:
    return _get(store.stages, "stage", stage_id)


def save_route(store, route: Route) -> Route:
    store.routes[route.id] = route
    return route


def get_route(store, route_id: str) -> Route:
    return _get(store.routes, "route", route_id)


def save_owner(store, owner: Owner) -> Owner:
    store.owners[owner.id] = owner
    return owner


def get_owner(store, owner_id: str) -> Owner:
    return _get(store.owners, "owner", owner_id)


def save_vehicle(store, vehicle: Vehicle) -> Vehicle:
    store.vehicles[vehicle.id] = vehicle
    return vehicle


def get_vehicle(store, vehicle_id: str) -> Vehicle:
    return _get(store.vehicles, "vehicle", vehicle_id)


def save_crew_member(store, member: CrewMember) -> CrewMember:
    store.crew[member.id] = member
    return member


def get_crew_member(store, crew_id: str) -> CrewMember:
    return _get(store.crew, "crew member", crew_id)


def save_shift(store, shift: Shift) -> Shift:
    store.shifts[shift.id] = shift
    return shift


def get_shift(store, shift_id: str) -> Shift:
    return _get(store.shifts, "shift", shift_id)


def save_trip(store, trip: Trip) -> Trip:
    store.trips[trip.id] = trip
    return trip


def get_trip(store, trip_id: str) -> Trip:
    return _get(store.trips, "trip", trip_id)


def save_ticket(store, ticket: Ticket) -> Ticket:
    store.tickets[ticket.id] = ticket
    return ticket


def get_ticket(store, ticket_id: str) -> Ticket:
    return _get(store.tickets, "ticket", ticket_id)


def tickets_on_trip(store, trip_id: str) -> List[Ticket]:
    return [ticket for ticket in store.tickets.values() if ticket.trip_id == trip_id]


def tickets_of_phone(store, phone: str) -> List[Ticket]:
    return [ticket for ticket in store.tickets.values() if ticket.phone == phone]


def save_day_pass(store, day_pass: DayPass) -> DayPass:
    store.day_passes[day_pass.id] = day_pass
    return day_pass


def get_day_pass(store, pass_id: str) -> DayPass:
    return _get(store.day_passes, "day pass", pass_id)


def save_refund(store, refund: Refund) -> Refund:
    store.refunds[refund.id] = refund
    return refund
