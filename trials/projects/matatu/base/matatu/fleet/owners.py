"""The people who own the vehicles."""

from typing import List

from ..models import Vehicle


def vehicles_of(store, owner_id: str) -> List[Vehicle]:
    return [vehicle for vehicle in store.vehicles.values() if vehicle.owner_id == owner_id]


def fleet_size(store, owner_id: str) -> int:
    return sum(1 for vehicle in vehicles_of(store, owner_id) if vehicle.active)
