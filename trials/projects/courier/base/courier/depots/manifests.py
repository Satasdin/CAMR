"""Grouping parcels into van loads."""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from ..models import STATUS_COLLECTED, Parcel
from .routes import route_between

VAN_CAPACITY_KG = 800
VAN_CAPACITY_PARCELS = 120


@dataclass
class Manifest:
    depot: str
    next_stop: str
    parcel_ids: List[str] = field(default_factory=list)
    weight_kg: float = 0.0

    def has_room_for(self, parcel: Parcel) -> bool:
        return len(self.parcel_ids) < VAN_CAPACITY_PARCELS and self.weight_kg + parcel.weight_kg <= VAN_CAPACITY_KG

    def add(self, parcel: Parcel) -> None:
        self.parcel_ids.append(parcel.id)
        self.weight_kg += parcel.weight_kg


def next_stop_for(parcel: Parcel, depot: str) -> str:
    route = route_between(depot, parcel.destination_zone)
    return route[1] if len(route) > 1 else depot


def ready_parcels(parcels: Iterable[Parcel], depot: str) -> List[Parcel]:
    return [p for p in parcels if p.status == STATUS_COLLECTED and p.origin_zone == depot]


def build_manifests(parcels: Iterable[Parcel], depot: str) -> List[Manifest]:
    """Heaviest parcels first, opening a new van for a stop when the last one is full."""
    by_stop: Dict[str, List[Manifest]] = {}
    for parcel in sorted(ready_parcels(parcels, depot), key=lambda p: (-p.weight_kg, p.id)):
        stop = next_stop_for(parcel, depot)
        vans = by_stop.setdefault(stop, [Manifest(depot=depot, next_stop=stop)])
        if not vans[-1].has_room_for(parcel):
            vans.append(Manifest(depot=depot, next_stop=stop))
        vans[-1].add(parcel)
    return [van for stop in sorted(by_stop) for van in by_stop[stop]]


def render_manifest(manifest: Manifest) -> str:
    rows = [f"Depot {manifest.depot} to {manifest.next_stop}: {len(manifest.parcel_ids)} parcels, {manifest.weight_kg:.1f} kg"]
    rows += [f"  {parcel_id}" for parcel_id in manifest.parcel_ids]
    return "\n".join(rows)
