"""Keeping track of the vehicles."""

from typing import List

from ..errors import VehicleNotRoadworthy
from ..models import Trip, Vehicle
from ..store.repositories import get_vehicle, save_trip, save_vehicle
from .inspections import is_overdue


def assign_to_route(store, vehicle_id: str, route_id: str) -> Vehicle:
    vehicle = get_vehicle(store, vehicle_id)
    vehicle.route_id = route_id
    return save_vehicle(store, vehicle)


def vehicles_on_route(store, route_id: str) -> List[Vehicle]:
    return [vehicle for vehicle in store.vehicles.values() if vehicle.route_id == route_id and vehicle.active]


def schedule_trip(store, vehicle_id: str, driver_id: str, conductor_id: str, departs_at: int, clock) -> Trip:
    vehicle = get_vehicle(store, vehicle_id)
    if is_overdue(vehicle, clock.now()):
        raise VehicleNotRoadworthy(vehicle_id)
    trip = Trip(id=store.next_id("TRP"), route_id=vehicle.route_id, vehicle_id=vehicle_id, driver_id=driver_id,
                conductor_id=conductor_id, departs_at=departs_at)
    return save_trip(store, trip)
