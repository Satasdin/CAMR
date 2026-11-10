"""How each route did."""

from typing import Dict, List, Tuple

from ..clock import day_of
from ..models import TICKET_PAID


def fares_by_route(store, day: str) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for ticket in store.tickets.values():
        if ticket.status == TICKET_PAID and day_of(ticket.issued_at) == day:
            totals[ticket.route_id] = totals.get(ticket.route_id, 0) + ticket.fare_kes
    return totals


def league_table(store, day: str) -> List[Tuple[str, int]]:
    """Routes from highest fares to lowest; ties in route order."""
    return sorted(fares_by_route(store, day).items(), key=lambda pair: (-pair[1], pair[0]))
