import unittest

from matatu.clock import moment_of
from matatu.fares.quote import quote_fare

MIDDAY = moment_of("2023-11-15", 11)


class Luggage(unittest.TestCase):
    def test_each_bag_after_the_first_is_charged(self):
        self.assertEqual(quote_fare(2, MIDDAY, bags=3).amount("luggage"), 40)

    def test_luggage_adds_to_the_total(self):
        self.assertEqual(quote_fare(2, MIDDAY, bags=4).total_kes - quote_fare(2, MIDDAY).total_kes, 60)

    def test_no_line_for_one_bag_or_none(self):
        for bags in (0, 1):
            self.assertNotIn("luggage", [name for name, _ in quote_fare(2, MIDDAY, bags=bags).lines])

    def test_rain_is_still_charged(self):
        result = quote_fare(2, MIDDAY, bags=2, raining=True)
        self.assertEqual(result.amount("rain"), 20)
        self.assertEqual(result.amount("luggage"), 20)
