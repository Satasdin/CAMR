"""Patients waiting for an earlier time with a doctor."""

from typing import List, Optional

from ..config import SECONDS_PER_HOUR, WAITLIST_OFFER_HOURS
from ..errors import ValidationFailed
from ..models import WaitlistEntry
from ..store.repositories import get_doctor, get_patient


def join_waitlist(store, patient_id: str, doctor_id: str, clock) -> WaitlistEntry:
    get_patient(store, patient_id)
    get_doctor(store, doctor_id)
    if any(e.patient_id == patient_id and e.doctor_id == doctor_id for e in store.waitlist):
        raise ValidationFailed(["that patient is already waiting for this doctor"])
    entry = WaitlistEntry(id=store.next_id("WLT"), patient_id=patient_id, doctor_id=doctor_id, added_at=clock.now())
    store.waitlist.append(entry)
    return entry


def waiting_for(store, doctor_id: str) -> List[WaitlistEntry]:
    found = [e for e in store.waitlist if e.doctor_id == doctor_id and e.offered_start is None]
    return sorted(found, key=lambda e: e.added_at)


def offer_next(store, doctor_id: str, start_at: int, clock) -> Optional[WaitlistEntry]:
    """Offers a freed time to whoever has waited longest, if anyone is waiting."""
    waiting = waiting_for(store, doctor_id)
    if not waiting:
        return None
    entry = waiting[0]
    entry.offered_start = start_at
    entry.offer_expires_at = clock.now() + WAITLIST_OFFER_HOURS * SECONDS_PER_HOUR
    return entry


def expire_offers(store, now: int) -> int:
    expired = [e for e in store.waitlist if e.offer_expires_at is not None and e.offer_expires_at < now]
    for entry in expired:
        entry.offered_start = None
        entry.offer_expires_at = None
    return len(expired)
