import unittest

from courier.api.handlers import Context, parcel_timeline
from courier.clock import FixedClock
from courier.models import Parcel
from courier.notify.sender import outbox_sender
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_parcel
from courier.tracking.events import import_scan


def context_with(*scans):
    store = InMemoryStore()
    save_parcel(store, Parcel(id="P1", customer_id="C1", origin_zone="NBO", destination_zone="MBA", weight_kg=2))
    for status, at in scans:
        import_scan(store, "P1", status, at)
    return Context(store=store, gateway=None, clock=FixedClock(), sender=outbox_sender(store))


class Current(unittest.TestCase):
    def test_current_is_the_most_recent_status(self):
        response = parcel_timeline({"parcel_id": "P1"}, context_with(("in_transit", 200), ("out_for_delivery", 300), ("collected", 100)))
        self.assertEqual(response["current"], "out_for_delivery")
        self.assertEqual(len(response["events"]), 3)

    def test_no_events_yet(self):
        response = parcel_timeline({"parcel_id": "P1"}, context_with())
        self.assertIsNone(response["current"])
        self.assertEqual(response["events"], [])
