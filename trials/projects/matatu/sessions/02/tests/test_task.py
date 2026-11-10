import unittest

from matatu.api.handlers import Context, day_close_report
from matatu.clock import FixedClock, moment_of
from matatu.models import TICKET_ISSUED, TICKET_PAID, Ticket
from matatu.notify.sender import outbox_sender
from matatu.reports.day_close import day_close
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_ticket


def add_ticket(store, identifier, route, fare, at, status=TICKET_PAID):
    save_ticket(store, Ticket(id=identifier, trip_id="TR1", route_id=route, vehicle_id="V1", from_stage="A", to_stage="B",
                              phone="+254700000001", fare_kes=fare, status=status, issued_at=at))


def store_with_tickets():
    store = InMemoryStore()
    add_ticket(store, "T1", "58", 80, moment_of("2023-11-15", 9))
    add_ticket(store, "T2", "58", 50, moment_of("2023-11-15", 14))
    add_ticket(store, "T3", "46", 120, moment_of("2023-11-15", 18))
    add_ticket(store, "T4", "46", 120, moment_of("2023-11-15", 19), status=TICKET_ISSUED)
    add_ticket(store, "T5", "46", 70, moment_of("2023-11-16", 9))
    return store


class DayClose(unittest.TestCase):
    def test_counts_the_paid_tickets_of_the_day(self):
        result = day_close(store_with_tickets(), "2023-11-15")
        self.assertEqual(result["day"], "2023-11-15")
        self.assertEqual(result["tickets"], 3)
        self.assertEqual(result["takings_kes"], 250)
        self.assertEqual(result["by_route"], {"58": 130, "46": 120})

    def test_a_day_with_nothing_on_it(self):
        result = day_close(InMemoryStore(), "2023-11-15")
        self.assertEqual((result["tickets"], result["takings_kes"], result["by_route"]), (0, 0, {}))

    def test_handler(self):
        store = store_with_tickets()
        context = Context(store=store, provider=None, clock=FixedClock(), sender=outbox_sender(store))
        self.assertEqual(day_close_report({"day": "2023-11-16"}, context)["takings_kes"], 70)

    def test_handler_needs_a_day(self):
        store = InMemoryStore()
        context = Context(store=store, provider=None, clock=FixedClock(), sender=outbox_sender(store))
        self.assertEqual(day_close_report({}, context)["error"], "invalid")
