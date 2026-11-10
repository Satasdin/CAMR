import unittest

from matatu.clock import FixedClock, moment_of
from matatu.store.memory import InMemoryStore
from matatu.tickets.passes import pass_is_valid, sell_day_pass

PHONE = "+254700000001"


def pass_bought_at(moment):
    store = InMemoryStore()
    return store, sell_day_pass(store, PHONE, FixedClock(moment)).id


class OperatingDay(unittest.TestCase):
    def test_bought_late_it_still_works_in_the_small_hours(self):
        store, pass_id = pass_bought_at(moment_of("2023-11-15", 22))
        self.assertTrue(pass_is_valid(store, pass_id, moment_of("2023-11-16", 1, 30)))

    def test_bought_in_the_small_hours_it_ends_at_three(self):
        store, pass_id = pass_bought_at(moment_of("2023-11-16", 1, 30))
        self.assertTrue(pass_is_valid(store, pass_id, moment_of("2023-11-16", 2, 30)))
        self.assertFalse(pass_is_valid(store, pass_id, moment_of("2023-11-16", 10)))
