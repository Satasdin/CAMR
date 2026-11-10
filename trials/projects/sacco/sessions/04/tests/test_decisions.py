import unittest

from sacco.clock import FixedClock
from sacco.members.registry import register_member
from sacco.savings.deposits import correct_deposit, deposit
from sacco.savings.ledger import entries_for
from sacco.store.memory import InMemoryStore
from sacco.store.repositories import account_of_member


def setup():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Wanjiku Kamau", "+254712000001", "w@x.example", "12345678", clock)
    deposit(store, member.id, 1_000_000, clock)
    mistyped = deposit(store, member.id, 500_000, clock)
    return store, clock, member, mistyped


class PostedLinesStayAsPosted(unittest.TestCase):
    def test_the_mistyped_line_is_still_there_unchanged(self):
        store, clock, member, mistyped = setup()
        correct_deposit(store, mistyped.id, 50_000, clock)
        kept = [entry for entry in store.ledger if entry.id == mistyped.id]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].amount_cents, 500_000)

    def test_the_correction_is_posted_as_further_lines(self):
        store, clock, member, mistyped = setup()
        correct_deposit(store, mistyped.id, 50_000, clock)
        entries = entries_for(store, account_of_member(store, member.id).id)
        self.assertGreater(len(entries), 2)
        self.assertEqual(sum(entry.amount_cents for entry in entries), 1_050_000)
