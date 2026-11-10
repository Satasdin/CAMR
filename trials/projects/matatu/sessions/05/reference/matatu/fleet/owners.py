"""The people who own the vehicles."""

from typing import Dict, List

from ..clock import operating_day
from ..config import SACCO_LEVY_PERCENT
from ..models import TICKET_PAID, Vehicle
from ..money import percent_of
from ..store.repositories import get_owner


def vehicles_of(store, owner_id: str) -> List[Vehicle]:
    return [vehicle for vehicle in store.vehicles.values() if vehicle.owner_id == owner_id]


def fleet_size(store, owner_id: str) -> int:
    return sum(1 for vehicle in vehicles_of(store, owner_id) if vehicle.active)


def owner_payout(store, owner_id: str, date: str) -> Dict:
    get_owner(store, owner_id)
    vehicle_ids = {vehicle.id for vehicle in vehicles_of(store, owner_id)}
    gross = sum(ticket.fare_kes for ticket in store.tickets.values()
                if ticket.vehicle_id in vehicle_ids and ticket.status == TICKET_PAID
                and operating_day(ticket.issued_at) == date)
    levy = percent_of(gross, SACCO_LEVY_PERCENT)
    return {"owner_id": owner_id, "date": date, "gross_kes": gross, "levy_kes": levy, "net_kes": gross - levy}
