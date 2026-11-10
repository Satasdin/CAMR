"""When vehicles are next due at the inspection centre."""

from typing import List

from ..config import INSPECTION_INTERVAL_DAYS, SECONDS_PER_DAY
from ..models import Vehicle
from ..store.repositories import save_vehicle


def next_due_at(vehicle: Vehicle) -> int:
    return vehicle.last_inspected_at + INSPECTION_INTERVAL_DAYS * SECONDS_PER_DAY


def is_overdue(vehicle: Vehicle, now: int) -> bool:
    return now > next_due_at(vehicle)


def record_inspection(store, vehicle: Vehicle, clock) -> Vehicle:
    vehicle.last_inspected_at = clock.now()
    return save_vehicle(store, vehicle)


def overdue_vehicles(store, now: int) -> List[Vehicle]:
    return [vehicle for vehicle in store.vehicles.values() if vehicle.active and is_overdue(vehicle, now)]
