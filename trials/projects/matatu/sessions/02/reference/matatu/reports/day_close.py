"""The figures the treasurer signs off for each day."""

from typing import Dict

from ..clock import operating_day
from ..models import TICKET_PAID


def day_close(store, day: str) -> Dict:
    tickets = [t for t in store.tickets.values() if t.status == TICKET_PAID and operating_day(t.issued_at) == day]
    by_route: Dict[str, int] = {}
    for ticket in tickets:
        by_route[ticket.route_id] = by_route.get(ticket.route_id, 0) + ticket.fare_kes
    return {"day": day, "tickets": len(tickets), "takings_kes": sum(t.fare_kes for t in tickets), "by_route": by_route}
