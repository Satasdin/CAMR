"""The figures sent to finance each morning."""

from collections import Counter
from dataclasses import dataclass
from typing import Dict

from ..clock import day_of
from ..models import METHOD_CASH, METHOD_MOBILE, TICKET_PAID, TICKET_REFUNDED
from ..money import format_kes


@dataclass
class DailyFigures:
    day: str
    tickets_paid: int
    cash_kes: int
    mobile_kes: int
    refunded_kes: int
    methods: Dict[str, int]

    def net_kes(self) -> int:
        return self.cash_kes + self.mobile_kes - self.refunded_kes


def figures_for(store, day: str) -> DailyFigures:
    paid = [t for t in store.tickets.values()
            if t.status in (TICKET_PAID, TICKET_REFUNDED) and t.paid_at is not None and day_of(t.paid_at) == day]
    counted = Counter(t.method for t in paid)
    return DailyFigures(day=day, tickets_paid=len(paid),
                        cash_kes=sum(t.fare_kes for t in paid if t.method == METHOD_CASH),
                        mobile_kes=sum(t.fare_kes for t in paid if t.method == METHOD_MOBILE),
                        refunded_kes=sum(t.fare_kes for t in paid if t.status == TICKET_REFUNDED),
                        methods=dict(counted))


def render_daily(figures: DailyFigures) -> str:
    return "\n".join([
        f"Daily figures for {figures.day}",
        f"Tickets paid: {figures.tickets_paid}",
        f"Cash: {format_kes(figures.cash_kes)}",
        f"Mobile money: {format_kes(figures.mobile_kes)}",
        f"Refunded: {format_kes(figures.refunded_kes)}",
        f"Net: {format_kes(figures.net_kes())}",
    ])
