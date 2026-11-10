"""The queue of walk-in patients waiting to be seen."""

from typing import List, Optional

from ..config import SECONDS_PER_MINUTE
from ..errors import InvalidTransition
from ..models import TRIAGE_SEEN, TRIAGE_WAITING, TriageCase, Vitals
from ..store.repositories import get_patient, get_triage_case, save_triage_case
from .levels import LEVEL_ORDER, level_for, target_minutes
from .scoring import score_vitals


def admit(store, patient_id: str, vitals: Vitals, clock) -> TriageCase:
    get_patient(store, patient_id)
    total = score_vitals(vitals).total
    case = TriageCase(id=store.next_id("TRG"), patient_id=patient_id, vitals=vitals, score=total,
                      level=level_for(total), arrived_at=clock.now())
    return save_triage_case(store, case)


def waiting(store) -> List[TriageCase]:
    found = [c for c in store.triage_cases.values() if c.status == TRIAGE_WAITING]
    return sorted(found, key=lambda c: (LEVEL_ORDER[c.level], c.arrived_at))


def next_case(store) -> Optional[TriageCase]:
    queue = waiting(store)
    return queue[0] if queue else None


def mark_seen(store, case_id: str, clock) -> TriageCase:
    case = get_triage_case(store, case_id)
    if case.status != TRIAGE_WAITING:
        raise InvalidTransition(case.status, TRIAGE_SEEN)
    case.status = TRIAGE_SEEN
    case.seen_at = clock.now()
    return save_triage_case(store, case)


def overdue(store, now: int) -> List[TriageCase]:
    return [c for c in waiting(store) if now - c.arrived_at > target_minutes(c.level) * SECONDS_PER_MINUTE]
