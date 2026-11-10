import unittest

from matatu.clock import moment_of
from matatu.models import TICKET_PAID, Ticket
from matatu.reports.day_close import day_close
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_ticket


def store_with(*moments):
    store = InMemoryStore()
    for index, moment in enumerate(moments):
        save_ticket(store, Ticket(id=f"T{index}", trip_id="TR1", route_id="58", vehicle_id="V1", from_stage="A", to_stage="B",
                                  phone="+254700000001", fare_kes=100, status=TICKET_PAID, issued_at=moment))
    return store


class OperatingDay(unittest.TestCase):
    def test_small_hours_belong_to_the_day_before(self):
        store = store_with(moment_of("2023-11-16", 1, 30))
        self.assertEqual(day_close(store, "2023-11-15")["tickets"], 1)
        self.assertEqual(day_close(store, "2023-11-16")["tickets"], 0)

    def test_the_day_turns_over_at_three(self):
        store = store_with(moment_of("2023-11-16", 2, 59), moment_of("2023-11-16", 3, 0))
        self.assertEqual(day_close(store, "2023-11-15")["tickets"], 1)
        self.assertEqual(day_close(store, "2023-11-16")["tickets"], 1)
