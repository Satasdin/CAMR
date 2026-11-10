import unittest

from matatu.clock import moment_of
from matatu.fleet.owners import owner_payout
from matatu.models import TICKET_PAID, Owner, Ticket, Vehicle
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_owner, save_ticket, save_vehicle


def store_with(moment):
    store = InMemoryStore()
    save_owner(store, Owner(id="O1", name="Wanjiru", phone="+254711000001"))
    save_vehicle(store, Vehicle(id="V1", plate="KDA 001A", owner_id="O1"))
    save_ticket(store, Ticket(id="T1", trip_id="TR1", route_id="58", vehicle_id="V1", from_stage="A", to_stage="B",
                              phone="+254700000001", fare_kes=500, status=TICKET_PAID, issued_at=moment))
    return store


class OperatingDay(unittest.TestCase):
    def test_a_ticket_in_the_small_hours_counts_for_the_day_before(self):
        store = store_with(moment_of("2023-11-16", 1, 30))
        self.assertEqual(owner_payout(store, "O1", "2023-11-15")["gross_kes"], 500)
        self.assertEqual(owner_payout(store, "O1", "2023-11-16")["gross_kes"], 0)

    def test_a_ticket_after_three_counts_for_its_own_day(self):
        store = store_with(moment_of("2023-11-16", 3, 30))
        self.assertEqual(owner_payout(store, "O1", "2023-11-16")["gross_kes"], 500)
