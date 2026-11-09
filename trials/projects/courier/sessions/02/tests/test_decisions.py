import unittest

from courier.models import Parcel
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_parcel
from courier.tracking.events import import_scan
from courier.tracking.timeline import build_timeline


class OldestFirst(unittest.TestCase):
    def test_timeline_is_oldest_first(self):
        store = InMemoryStore()
        save_parcel(store, Parcel(id="P1", customer_id="C1", origin_zone="NBO", destination_zone="MBA", weight_kg=2))
        import_scan(store, "P1", "in_transit", 200)
        import_scan(store, "P1", "collected", 100)
        import_scan(store, "P1", "out_for_delivery", 300)
        self.assertEqual([event["at"] for event in build_timeline(store, "P1")], [100, 200, 300])
