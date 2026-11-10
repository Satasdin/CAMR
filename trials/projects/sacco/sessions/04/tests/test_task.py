import unittest

from sacco.clock import FixedClock
from sacco.errors import NotFound, ValidationFailed
from sacco.members.registry import register_member
from sacco.savings.accounts import savings_balance
from sacco.savings.deposits import correct_deposit, deposit
from sacco.savings.withdrawals import withdraw
from sacco.statements.member import member_statement
from sacco.store.memory import InMemoryStore


def setup():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Wanjiku Kamau", "+254712000001", "w@x.example", "12345678", clock)
    deposit(store, member.id, 1_000_000, clock)
    mistyped = deposit(store, member.id, 500_000, clock)
    return store, clock, member, mistyped


class Correcting(unittest.TestCase):
    def test_balance_shows_the_right_amount(self):
        store, clock, member, mistyped = setup()
        self.assertEqual(correct_deposit(store, mistyped.id, 50_000, clock), 1_050_000)
        self.assertEqual(savings_balance(store, member.id), 1_050_000)

    def test_statement_closes_on_the_right_amount(self):
        store, clock, member, mistyped = setup()
        correct_deposit(store, mistyped.id, 50_000, clock)
        statement = member_statement(store, member.id, 0, clock.now() + 1)
        self.assertEqual(statement["closing_balance_cents"], 1_050_000)

    def test_only_deposits_can_be_corrected(self):
        store, clock, member, mistyped = setup()
        taken = withdraw(store, member.id, 100_000, clock)
        with self.assertRaises(ValidationFailed):
            correct_deposit(store, taken.id, 50_000, clock)

    def test_amount_must_be_positive(self):
        store, clock, member, mistyped = setup()
        with self.assertRaises(ValidationFailed):
            correct_deposit(store, mistyped.id, 0, clock)

    def test_unknown_entry(self):
        store, clock, member, mistyped = setup()
        with self.assertRaises(NotFound):
            correct_deposit(store, "ENT-NOPE", 50_000, clock)
