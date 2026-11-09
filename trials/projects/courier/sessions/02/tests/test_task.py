import unittest

from courier.api.handlers import Context, parcel_timeline
from courier.clock import FixedClock
from courier.errors import NotFound
from courier.models import Parcel
from courier.notify.sender import outbox_sender
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_parcel
from courier.tracking.events import import_scan
from courier.tracking.timeline import build_timeline


def store_with_events():
    store = InMemoryStore()
    save_parcel(store, Parcel(id="P1", customer_id="C1", origin_zone="NBO", destination_zone="MBA", weight_kg=2))
    import_scan(store, "P1", "in_transit", 200, "Nakuru hub")
    import_scan(store, "P1", "collected", 100, "picked up")
    import_scan(store, "P1", "out_for_delivery", 300)
    return store


class Timeline(unittest.TestCase):
    def test_every_event_is_returned_with_its_fields(self):
        events = build_timeline(store_with_events(), "P1")
        self.assertEqual(len(events), 3)
        self.assertEqual(set(events[0]), {"status", "at", "note"})

    def test_unknown_parcel(self):
        with self.assertRaises(NotFound):
            build_timeline(InMemoryStore(), "NOPE")

    def test_handler(self):
        store = store_with_events()
        context = Context(store=store, gateway=None, clock=FixedClock(), sender=outbox_sender(store))
        response = parcel_timeline({"parcel_id": "P1"}, context)
        self.assertEqual(response["parcel_id"], "P1")
        self.assertEqual(len(response["events"]), 3)

    def test_handler_reports_a_missing_parcel(self):
        store = InMemoryStore()
        context = Context(store=store, gateway=None, clock=FixedClock(), sender=outbox_sender(store))
        self.assertEqual(parcel_timeline({"parcel_id": "NOPE"}, context)["error"], "not_found")
