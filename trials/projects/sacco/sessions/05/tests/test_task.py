import unittest

from sacco.clock import FixedClock
from sacco.members.registry import register_member
from sacco.savings.deposits import deposit
from sacco.savings.reversals import reverse_entry
from sacco.statements.member import member_statement
from sacco.store.memory import InMemoryStore


def setup():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Wanjiku Kamau", "+254712000001", "w@x.example", "12345678", clock)
    deposit(store, member.id, 20_000, clock)
    wrong = deposit(store, member.id, 50_000, clock)
    return store, clock, member, wrong


class ReversedCount(unittest.TestCase):
    def test_counts_what_was_undone(self):
        store, clock, member, wrong = setup()
        reverse_entry(store, wrong.id, "wrong member", clock)
        statement = member_statement(store, member.id, 0, clock.now() + 1)
        self.assertEqual(statement["reversed_count"], 1)
        self.assertEqual(statement["closing_balance_cents"], 20_000)

    def test_zero_when_nothing_was_undone(self):
        store, clock, member, wrong = setup()
        statement = member_statement(store, member.id, 0, clock.now() + 1)
        self.assertEqual(statement["reversed_count"], 0)
        self.assertEqual(statement["closing_balance_cents"], 70_000)

    def test_a_later_undo_is_not_counted_in_an_earlier_period(self):
        store, clock, member, wrong = setup()
        end = clock.advance(100)
        clock.advance(100)
        reverse_entry(store, wrong.id, "wrong member", clock)
        self.assertEqual(member_statement(store, member.id, 0, end)["reversed_count"], 0)
