"""Weekly totals built from the daily figures."""

from datetime import datetime, timedelta
from typing import List

from ..money import format_cents
from .daily import DailyFigures, figures_for


def seven_days_from(start_day: str) -> List[str]:
    start = datetime.strptime(start_day, "%Y-%m-%d")
    return [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(7)]


def weekly_figures(store, start_day: str) -> List[DailyFigures]:
    return [figures_for(store, day) for day in seven_days_from(start_day)]


def delivery_rate(week: List[DailyFigures]) -> float:
    delivered = sum(day.delivered for day in week)
    attempted = delivered + sum(day.failed for day in week)
    return delivered / attempted if attempted else 0.0


def busiest_day(week: List[DailyFigures]) -> str:
    return max(week, key=lambda day: day.invoices_paid).day


def render_weekly(week: List[DailyFigures]) -> str:
    total = sum(day.revenue_cents for day in week)
    refunded = sum(day.refunded_cents for day in week)
    return "\n".join([
        f"Week of {week[0].day}",
        f"Revenue: {format_cents(total)}",
        f"Refunded: {format_cents(refunded)}",
        f"Net: {format_cents(total - refunded)}",
        f"Delivery rate: {delivery_rate(week):.0%}",
        f"Busiest day: {busiest_day(week)}",
    ])
