import unittest

from matatu.clock import moment_of
from matatu.errors import NotFound
from matatu.fleet.owners import owner_payout
from matatu.models import TICKET_ISSUED, TICKET_PAID, Owner, Ticket, Vehicle
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_owner, save_ticket, save_vehicle


def add_ticket(store, identifier, vehicle, fare, at, status=TICKET_PAID):
    save_ticket(store, Ticket(id=identifier, trip_id="TR1", route_id="46", vehicle_id=vehicle, from_stage="A", to_stage="B",
                              phone="+254700000001", fare_kes=fare, status=status, issued_at=at))


def fleet():
    store = InMemoryStore()
    save_owner(store, Owner(id="O1", name="Wanjiru", phone="+254711000001"))
    save_owner(store, Owner(id="O2", name="Otieno", phone="+254711000002"))
    save_vehicle(store, Vehicle(id="V1", plate="KDA 001A", owner_id="O1"))
    save_vehicle(store, Vehicle(id="V2", plate="KDA 002B", owner_id="O1"))
    save_vehicle(store, Vehicle(id="V3", plate="KDA 003C", owner_id="O2"))
    return store


class OwnerPayout(unittest.TestCase):
    def test_adds_up_the_owners_vehicles(self):
        store = fleet()
        add_ticket(store, "T1", "V1", 600, moment_of("2023-11-15", 9))
        add_ticket(store, "T2", "V2", 400, moment_of("2023-11-15", 14))
        add_ticket(store, "T3", "V3", 900, moment_of("2023-11-15", 15))
        add_ticket(store, "T4", "V1", 200, moment_of("2023-11-15", 16), status=TICKET_ISSUED)
        add_ticket(store, "T5", "V1", 300, moment_of("2023-11-16", 12))
        result = owner_payout(store, "O1", "2023-11-15")
        self.assertEqual(result, {"owner_id": "O1", "date": "2023-11-15", "gross_kes": 1000, "levy_kes": 80, "net_kes": 920})

    def test_nothing_earned(self):
        result = owner_payout(fleet(), "O2", "2023-11-15")
        self.assertEqual((result["gross_kes"], result["levy_kes"], result["net_kes"]), (0, 0, 0))

    def test_unknown_owner(self):
        with self.assertRaises(NotFound):
            owner_payout(fleet(), "NOPE", "2023-11-15")
