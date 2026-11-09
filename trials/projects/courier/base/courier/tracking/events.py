"""Recording what happens to a parcel."""

from typing import List

from ..models import STATUS_DELIVERED, TrackingEvent
from ..store.repositories import get_parcel, save_parcel
from .status import check_transition


def events_for(store, parcel_id: str) -> List[TrackingEvent]:
    """Events in the order they were recorded, which is not always the order they happened."""
    return [event for event in store.events if event.parcel_id == parcel_id]


def record_event(store, parcel_id: str, status: str, at: int, note: str = "") -> TrackingEvent:
    """Moves a parcel to a new status and keeps the event."""
    parcel = get_parcel(store, parcel_id)
    check_transition(parcel.status, status)
    event = TrackingEvent(parcel_id=parcel_id, status=status, at=at, note=note)
    store.events.append(event)
    parcel.status = status
    if status == STATUS_DELIVERED:
        parcel.delivered_at = at
    save_parcel(store, parcel)
    return event


def import_scan(store, parcel_id: str, status: str, at: int, note: str = "") -> TrackingEvent:
    """Adds a scan uploaded late by a depot. It is kept, but does not move the parcel."""
    get_parcel(store, parcel_id)
    event = TrackingEvent(parcel_id=parcel_id, status=status, at=at, note=note)
    store.events.append(event)
    return event
