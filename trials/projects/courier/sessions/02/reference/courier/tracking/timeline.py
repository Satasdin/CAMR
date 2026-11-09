"""A parcel's history, ready to show."""

from typing import Dict, List

from ..store.repositories import get_parcel
from .events import events_for


def build_timeline(store, parcel_id: str) -> List[Dict]:
    get_parcel(store, parcel_id)
    ordered = sorted(events_for(store, parcel_id), key=lambda event: event.at)
    return [{"status": event.status, "at": event.at, "note": event.note} for event in ordered]
