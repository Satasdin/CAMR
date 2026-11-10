"""A week's visits by department."""

from collections import Counter
from typing import Dict, List

from ..clock import day_of
from ..config import SECONDS_PER_DAY
from ..models import APPOINTMENT_COMPLETED
from ..store.repositories import get_doctor


def days_of_week(first_moment: int) -> List[str]:
    return [day_of(first_moment + offset * SECONDS_PER_DAY) for offset in range(7)]


def visits_by_department(store, first_moment: int) -> Dict[str, int]:
    days = set(days_of_week(first_moment))
    counted: Counter = Counter()
    for appointment in store.appointments.values():
        if appointment.status == APPOINTMENT_COMPLETED and day_of(appointment.start_at) in days:
            counted[get_doctor(store, appointment.doctor_id).department] += 1
    return dict(counted)


def render_weekly(counts: Dict[str, int]) -> str:
    rows = ["Visits by department"]
    rows += [f"  {department}: {counts[department]}" for department in sorted(counts)]
    rows.append(f"Total: {sum(counts.values())}")
    return "\n".join(rows)
