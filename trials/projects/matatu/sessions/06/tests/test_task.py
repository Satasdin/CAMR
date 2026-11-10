import unittest

from matatu.api.handlers import Context, check_day_pass
from matatu.clock import FixedClock, moment_of
from matatu.errors import NotFound
from matatu.notify.sender import outbox_sender
from matatu.store.memory import InMemoryStore
from matatu.tickets.passes import pass_is_valid, sell_day_pass

PHONE = "+254700000001"


class DayPass(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStore()
        self.day_pass = sell_day_pass(self.store, PHONE, FixedClock(moment_of("2023-11-15", 10)))

    def test_good_later_the_same_day(self):
        self.assertIs(pass_is_valid(self.store, self.day_pass.id, moment_of("2023-11-15", 16)), True)

    def test_not_good_the_following_day(self):
        self.assertIs(pass_is_valid(self.store, self.day_pass.id, moment_of("2023-11-16", 10)), False)

    def test_unknown_pass(self):
        with self.assertRaises(NotFound):
            pass_is_valid(self.store, "NOPE", moment_of("2023-11-15", 16))

    def test_handler_uses_the_clock(self):
        context = Context(store=self.store, provider=None, clock=FixedClock(moment_of("2023-11-15", 18)),
                          sender=outbox_sender(self.store))
        self.assertEqual(check_day_pass({"pass_id": self.day_pass.id}, context), {"pass_id": self.day_pass.id, "valid": True})
        context.clock = FixedClock(moment_of("2023-11-17", 18))
        self.assertEqual(check_day_pass({"pass_id": self.day_pass.id}, context)["valid"], False)

    def test_handler_reports_a_missing_pass(self):
        context = Context(store=self.store, provider=None, clock=FixedClock(), sender=outbox_sender(self.store))
        self.assertEqual(check_day_pass({"pass_id": "NOPE"}, context)["error"], "not_found")
