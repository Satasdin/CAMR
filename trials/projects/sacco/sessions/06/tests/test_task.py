import unittest
from dataclasses import replace

from sacco.clock import FixedClock
from sacco.loans.disbursement import disburse_loan
from sacco.loans.fees import fee_income_for
from sacco.loans.mpesa import SandboxMpesa
from sacco.loans.schedule import total_repayable
from sacco.members.registry import register_member
from sacco.models import LOAN_APPROVED, Loan
from sacco.savings.accounts import savings_balance
from sacco.savings.deposits import deposit
from sacco.store.memory import InMemoryStore
from sacco.store.repositories import get_loan, save_loan

APPROVED = 10_000_000
FEE = 150_000


def setup():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Otieno Odhiambo", "+254722000002", "o@x.example", "23456789", clock)
    deposit(store, member.id, 5_000_000, clock)
    save_loan(store, Loan(id="L1", member_id=member.id, product="normal", principal_cents=APPROVED,
                          term_months=12, monthly_rate_bp=100, status=LOAN_APPROVED))
    return store, clock, member


class FullAmountReachesThePhone(unittest.TestCase):
    def test_the_transfer_is_the_full_amount(self):
        store, clock, member = setup()
        gateway = SandboxMpesa()
        done = disburse_loan(store, "L1", gateway, clock)
        self.assertEqual(gateway.transfers[-1].amount_cents, APPROVED)
        self.assertEqual(done.sent_cents, APPROVED)

    def test_income_is_booked_as_before(self):
        store, clock, member = setup()
        disburse_loan(store, "L1", SandboxMpesa(), clock)
        self.assertEqual(fee_income_for(store, "L1"), FEE)

    def test_the_member_still_bears_the_charge_somewhere(self):
        store, clock, member = setup()
        savings_before = savings_balance(store, member.id)
        baseline = replace(get_loan(store, "L1"))
        disburse_loan(store, "L1", SandboxMpesa(), clock)
        savings_given_up = savings_before - savings_balance(store, member.id)
        extra_to_repay = total_repayable(get_loan(store, "L1")) - total_repayable(baseline)
        self.assertGreaterEqual(savings_given_up + extra_to_repay, FEE)
