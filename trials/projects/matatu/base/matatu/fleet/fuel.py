"""What the vehicles burn."""

from typing import List

from ..clock import day_of
from ..models import FuelFill
from ..store.repositories import get_vehicle


def record_fill(store, vehicle_id: str, litres: int, cost_kes: int, clock) -> FuelFill:
    get_vehicle(store, vehicle_id)
    fill = FuelFill(vehicle_id=vehicle_id, litres=litres, cost_kes=cost_kes, at=clock.now())
    store.fuel_fills.append(fill)
    return fill


def fills_on(store, day: str) -> List[FuelFill]:
    return [fill for fill in store.fuel_fills if day_of(fill.at) == day]


def fuel_cost_on(store, vehicle_id: str, day: str) -> int:
    return sum(fill.cost_kes for fill in fills_on(store, day) if fill.vehicle_id == vehicle_id)
