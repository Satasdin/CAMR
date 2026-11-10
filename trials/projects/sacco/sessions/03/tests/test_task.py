import unittest

from sacco.clock import FixedClock
from sacco.config import SECONDS_PER_DAY
from sacco.errors import ValidationFailed
from sacco.loans.applications import apply_for_loan
from sacco.loans.eligibility import loan_limit
from sacco.loans.products import PRODUCTS, product
from sacco.members.registry import register_member
from sacco.members.shares import buy_shares
from sacco.savings.deposits import deposit
from sacco.store.memory import InMemoryStore
from sacco.store.repositories import get_member


def established_member():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Amina Hassan", "+254733000003", "a@x.example", "34567890", clock)
    clock.advance(200 * SECONDS_PER_DAY)
    buy_shares(store, member.id, 25)
    deposit(store, member.id, 10_000_000, clock)
    return store, clock, get_member(store, member.id)


class SchoolFees(unittest.TestCase):
    def test_the_product_is_offered(self):
        found = product("school_fees")
        self.assertEqual((found.label, found.monthly_rate_bp, found.max_term_months), ("School Fees", 100, 12))

    def test_limit_is_twice_savings(self):
        store, clock, member = established_member()
        self.assertEqual(loan_limit(store, member, product("school_fees")), 20_000_000)

    def test_a_member_can_apply(self):
        store, clock, member = established_member()
        loan = apply_for_loan(store, member.id, "school_fees", 15_000_000, 12, clock)
        self.assertEqual(loan.monthly_rate_bp, 100)

    def test_terms_longer_than_a_year_are_refused(self):
        store, clock, member = established_member()
        with self.assertRaises(ValidationFailed):
            apply_for_loan(store, member.id, "school_fees", 1_000_000, 13, clock)

    def test_other_products_are_unchanged(self):
        self.assertEqual(sorted(PRODUCTS), ["development", "emergency", "normal", "school_fees"])
        self.assertEqual(product("normal").savings_multiple, 3)
