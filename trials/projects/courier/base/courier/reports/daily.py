"""The figures sent to finance each morning."""

from collections import Counter
from dataclasses import dataclass
from typing import Dict

from ..clock import day_of
from ..models import INVOICE_PAID, INVOICE_REFUNDED, STATUS_DELIVERED, STATUS_FAILED
from ..money import format_cents


@dataclass
class DailyFigures:
    day: str
    invoices_paid: int
    revenue_cents: int
    refunded_cents: int
    delivered: int
    failed: int
    statuses: Dict[str, int]

    def net_cents(self) -> int:
        return self.revenue_cents - self.refunded_cents


def figures_for(store, day: str) -> DailyFigures:
    paid = [i for i in store.invoices.values()
            if i.status in (INVOICE_PAID, INVOICE_REFUNDED) and i.paid_at is not None and day_of(i.paid_at) == day]
    events = [e for e in store.events if day_of(e.at) == day]
    counted = Counter(e.status for e in events)
    return DailyFigures(day=day, invoices_paid=len(paid), revenue_cents=sum(i.total_cents for i in paid),
                        refunded_cents=sum(i.refunded_cents for i in paid),
                        delivered=counted[STATUS_DELIVERED], failed=counted[STATUS_FAILED], statuses=dict(counted))


def render_daily(figures: DailyFigures) -> str:
    return "\n".join([
        f"Daily figures for {figures.day}",
        f"Invoices paid: {figures.invoices_paid}",
        f"Revenue: {format_cents(figures.revenue_cents)}",
        f"Refunded: {format_cents(figures.refunded_cents)}",
        f"Net: {format_cents(figures.net_cents())}",
        f"Delivered: {figures.delivered}",
        f"Failed deliveries: {figures.failed}",
    ])
