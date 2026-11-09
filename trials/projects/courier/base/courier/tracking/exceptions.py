"""Finding parcels that need chasing."""

from dataclasses import dataclass
from typing import Iterable, List

from ..config import SECONDS_PER_DAY
from ..models import STATUS_FAILED, Parcel
from .eta import is_late
from .events import events_for
from .status import is_finished

STALE_AFTER_DAYS = 2
MAX_DELIVERY_ATTEMPTS = 3


@dataclass
class Exception_:
    parcel_id: str
    kind: str
    detail: str


def last_event_at(store, parcel: Parcel) -> int:
    moments = [event.at for event in events_for(store, parcel.id)]
    return max(moments) if moments else parcel.created_at


def failed_attempts(store, parcel_id: str) -> int:
    return sum(1 for event in events_for(store, parcel_id) if event.status == STATUS_FAILED)


def exceptions_for(store, parcel: Parcel, now: int) -> List[Exception_]:
    if is_finished(parcel.status):
        return []
    found = []
    if is_late(parcel, now):
        found.append(Exception_(parcel.id, "late", "past its expected arrival"))
    if now - last_event_at(store, parcel) > STALE_AFTER_DAYS * SECONDS_PER_DAY:
        found.append(Exception_(parcel.id, "stale", f"no scan for {STALE_AFTER_DAYS} days"))
    attempts = failed_attempts(store, parcel.id)
    if attempts >= MAX_DELIVERY_ATTEMPTS:
        found.append(Exception_(parcel.id, "undeliverable", f"{attempts} failed attempts"))
    return found


def all_exceptions(store, parcels: Iterable[Parcel], now: int) -> List[Exception_]:
    return [item for parcel in parcels for item in exceptions_for(store, parcel, now)]


def summary_by_kind(items: Iterable[Exception_]) -> dict:
    out: dict = {}
    for item in items:
        out[item.kind] = out.get(item.kind, 0) + 1
    return out
