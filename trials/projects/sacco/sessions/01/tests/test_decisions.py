import unittest

from sacco.clock import FixedClock
from sacco.members.registry import register_member
from sacco.savings.deposits import deposit
from sacco.savings.ledger import entries_for
from sacco.savings.reversals import reverse_entry
from sacco.store.memory import InMemoryStore
from sacco.store.repositories import account_of_member


def setup():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Wanjiku Kamau", "+254712000001", "w@x.example", "12345678", clock)
    deposit(store, member.id, 20_000, clock)
    wrong = deposit(store, member.id, 50_000, clock)
    return store, clock, member, wrong


class ReversalsPostANewLine(unittest.TestCase):
    def test_the_original_line_stays_as_posted(self):
        store, clock, member, wrong = setup()
        reverse_entry(store, wrong.id, "wrong member", clock)
        kept = [entry for entry in store.ledger if entry.id == wrong.id]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].amount_cents, 50_000)

    def test_the_reversal_is_its_own_opposite_line(self):
        store, clock, member, wrong = setup()
        reverse_entry(store, wrong.id, "wrong member", clock)
        entries = entries_for(store, account_of_member(store, member.id).id)
        self.assertEqual([entry.amount_cents for entry in entries], [20_000, 50_000, -50_000])
