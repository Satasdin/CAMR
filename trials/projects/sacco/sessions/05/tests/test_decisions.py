import unittest

from sacco.clock import FixedClock
from sacco.members.registry import register_member
from sacco.savings.deposits import deposit
from sacco.savings.reversals import reverse_entry
from sacco.statements.member import member_statement
from sacco.store.memory import InMemoryStore


class EveryLineStaysOnTheStatement(unittest.TestCase):
    def test_the_money_going_in_and_back_out_are_both_listed(self):
        store = InMemoryStore()
        clock = FixedClock()
        member = register_member(store, "Wanjiku Kamau", "+254712000001", "w@x.example", "12345678", clock)
        deposit(store, member.id, 20_000, clock)
        wrong = deposit(store, member.id, 50_000, clock)
        reverse_entry(store, wrong.id, "wrong member", clock)
        lines = member_statement(store, member.id, 0, clock.now() + 1)["lines"]
        self.assertEqual([line["amount_cents"] for line in lines], [20_000, 50_000, -50_000])
