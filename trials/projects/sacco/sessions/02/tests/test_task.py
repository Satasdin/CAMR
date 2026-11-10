import unittest

from sacco.clock import FixedClock
from sacco.errors import InvalidLoanState
from sacco.loans.disbursement import PROCESSING_FEE_BASIS_POINTS, disburse_loan
from sacco.loans.fees import fee_income_for
from sacco.loans.mpesa import SandboxMpesa
from sacco.members.registry import register_member
from sacco.models import LOAN_ACTIVE, LOAN_APPLIED, LOAN_APPROVED, Loan
from sacco.money import basis_points_of
from sacco.savings.deposits import deposit
from sacco.store.memory import InMemoryStore
from sacco.store.repositories import get_loan, save_loan


def setup(status=LOAN_APPROVED, principal=10_000_000):
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Otieno Odhiambo", "+254722000002", "o@x.example", "23456789", clock)
    deposit(store, member.id, 5_000_000, clock)
    save_loan(store, Loan(id="L1", member_id=member.id, product="normal", principal_cents=principal,
                          term_months=12, monthly_rate_bp=100, status=status))
    return store, clock, member


class ProcessingFee(unittest.TestCase):
    def test_fee_is_one_and_a_half_percent(self):
        store, clock, member = setup()
        self.assertEqual(PROCESSING_FEE_BASIS_POINTS, 150)
        self.assertEqual(disburse_loan(store, "L1", SandboxMpesa(), clock).fee_cents, 150_000)

    def test_fee_rounds_with_the_money_helper(self):
        store, clock, member = setup(principal=3_333)
        self.assertEqual(disburse_loan(store, "L1", SandboxMpesa(), clock).fee_cents, basis_points_of(3_333, 150))

    def test_fee_is_booked_as_income(self):
        store, clock, member = setup()
        disburse_loan(store, "L1", SandboxMpesa(), clock)
        self.assertEqual(fee_income_for(store, "L1"), 150_000)

    def test_loan_goes_active(self):
        store, clock, member = setup()
        done = disburse_loan(store, "L1", SandboxMpesa(), clock)
        self.assertEqual(get_loan(store, "L1").status, LOAN_ACTIVE)
        self.assertTrue(done.receipt_id)

    def test_a_loan_not_approved_is_refused(self):
        store, clock, member = setup(status=LOAN_APPLIED)
        with self.assertRaises(InvalidLoanState):
            disburse_loan(store, "L1", SandboxMpesa(), clock)
