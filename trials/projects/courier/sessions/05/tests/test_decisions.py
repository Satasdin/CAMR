import unittest

from courier.api.handlers import Context, parcel_timeline
from courier.clock import FixedClock
from courier.models import Parcel
from courier.notify.sender import outbox_sender
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_parcel
from courier.tracking.events import import_scan
from courier.tracking.timeline import build_timeline


def store_with_events():
    store = InMemoryStore()
    save_parcel(store, Parcel(id="P1", customer_id="C1", origin_zone="NBO", destination_zone="MBA", weight_kg=2))
    import_scan(store, "P1", "in_transit", 200)
    import_scan(store, "P1", "out_for_delivery", 300)
    import_scan(store, "P1", "collected", 100)
    return store


class OldestFirst(unittest.TestCase):
    def test_response_events_stay_oldest_first(self):
        store = store_with_events()
        context = Context(store=store, gateway=None, clock=FixedClock(), sender=outbox_sender(store))
        self.assertEqual([event["at"] for event in parcel_timeline({"parcel_id": "P1"}, context)["events"]], [100, 200, 300])

    def test_build_timeline_stays_oldest_first(self):
        self.assertEqual([event["at"] for event in build_timeline(store_with_events(), "P1")], [100, 200, 300])
