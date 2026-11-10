import unittest

from sacco.api.handlers import Context, reverse_posting
from sacco.clock import FixedClock
from sacco.errors import AlreadyReversed, NotFound
from sacco.members.registry import register_member
from sacco.notify.sender import outbox_sender
from sacco.savings.accounts import savings_balance
from sacco.savings.deposits import deposit
from sacco.savings.reversals import reverse_entry
from sacco.store.memory import InMemoryStore


def setup():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Wanjiku Kamau", "+254712000001", "w@x.example", "12345678", clock)
    deposit(store, member.id, 20_000, clock)
    wrong = deposit(store, member.id, 50_000, clock)
    return store, clock, member, wrong


class Reversing(unittest.TestCase):
    def test_balance_goes_back_and_is_returned(self):
        store, clock, member, wrong = setup()
        self.assertEqual(reverse_entry(store, wrong.id, "wrong member", clock), 20_000)
        self.assertEqual(savings_balance(store, member.id), 20_000)

    def test_cannot_reverse_twice(self):
        store, clock, member, wrong = setup()
        reverse_entry(store, wrong.id, "wrong member", clock)
        with self.assertRaises(AlreadyReversed):
            reverse_entry(store, wrong.id, "wrong member again", clock)

    def test_unknown_entry(self):
        store, clock, member, wrong = setup()
        with self.assertRaises(NotFound):
            reverse_entry(store, "ENT-NOPE", "wrong member", clock)

    def test_handler(self):
        store, clock, member, wrong = setup()
        context = Context(store=store, gateway=None, clock=clock, sender=outbox_sender(store))
        response = reverse_posting({"entry_id": wrong.id, "reason": "wrong member"}, context)
        self.assertEqual(response, {"entry_id": wrong.id, "balance_cents": 20_000})

    def test_handler_reports_a_missing_entry(self):
        store, clock, member, wrong = setup()
        context = Context(store=store, gateway=None, clock=clock, sender=outbox_sender(store))
        self.assertEqual(reverse_posting({"entry_id": "ENT-NOPE", "reason": "x"}, context)["error"], "not_found")
