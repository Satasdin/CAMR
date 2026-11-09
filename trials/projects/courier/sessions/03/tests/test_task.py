import unittest

from courier.models import Parcel
from courier.pricing.quote import quote_parcel


def parcel(fragile):
    return Parcel(id="P1", customer_id="C1", origin_zone="NBO", destination_zone="MBA", weight_kg=2, fragile=fragile)


class Fragile(unittest.TestCase):
    def test_fragile_adds_the_surcharge(self):
        self.assertEqual(quote_parcel(parcel(True)).total_cents - quote_parcel(parcel(False)).total_cents, 15_000)

    def test_fragile_line_is_named(self):
        self.assertEqual(quote_parcel(parcel(True)).amount("fragile"), 15_000)

    def test_other_parcels_have_no_line(self):
        self.assertNotIn("fragile", [name for name, _ in quote_parcel(parcel(False)).lines])
