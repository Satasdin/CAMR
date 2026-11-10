"""The figures sent to management each morning."""

from collections import Counter
from dataclasses import dataclass
from typing import Dict

from ..clock import day_of
from ..models import APPOINTMENT_COMPLETED, APPOINTMENT_NO_SHOW, INVOICE_PAID
from ..money import format_cents


@dataclass
class DailyFigures:
    day: str
    visits: int
    no_shows: int
    revenue_cents: int
    statuses: Dict[str, int]

    def attendance_percent(self) -> int:
        booked = self.visits + self.no_shows
        return (self.visits * 100) // booked if booked else 0


def figures_for(store, day: str) -> DailyFigures:
    todays = [a for a in store.appointments.values() if day_of(a.start_at) == day]
    counted = Counter(a.status for a in todays)
    paid = [i for i in store.invoices.values() if i.status == INVOICE_PAID and day_of(i.created_at) == day]
    return DailyFigures(day=day, visits=counted[APPOINTMENT_COMPLETED], no_shows=counted[APPOINTMENT_NO_SHOW],
                        revenue_cents=sum(i.total_cents for i in paid), statuses=dict(counted))


def render_daily(figures: DailyFigures) -> str:
    return "\n".join([
        f"Daily figures for {figures.day}",
        f"Visits: {figures.visits}",
        f"No-shows: {figures.no_shows}",
        f"Attendance: {figures.attendance_percent()}%",
        f"Revenue: {format_cents(figures.revenue_cents)}",
    ])
