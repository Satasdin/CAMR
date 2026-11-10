import unittest

from sacco.clock import FixedClock
from sacco.loans.disbursement import disburse_loan
from sacco.loans.mpesa import SandboxMpesa
from sacco.loans.schedule import loan_schedule
from sacco.members.registry import register_member
from sacco.models import LOAN_APPROVED, Loan
from sacco.savings.deposits import deposit
from sacco.store.memory import InMemoryStore
from sacco.store.repositories import get_loan, save_loan


def setup():
    store = InMemoryStore()
    clock = FixedClock()
    member = register_member(store, "Otieno Odhiambo", "+254722000002", "o@x.example", "23456789", clock)
    deposit(store, member.id, 5_000_000, clock)
    save_loan(store, Loan(id="L1", member_id=member.id, product="normal", principal_cents=10_000_000,
                          term_months=12, monthly_rate_bp=100, status=LOAN_APPROVED))
    return store, clock


class PrincipalIsTheApprovedSum(unittest.TestCase):
    def test_principal_is_unchanged(self):
        store, clock = setup()
        disburse_loan(store, "L1", SandboxMpesa(), clock)
        loan = get_loan(store, "L1")
        self.assertEqual(loan.principal_cents, 10_000_000)
        self.assertEqual(loan.outstanding_principal_cents, 10_000_000)

    def test_schedule_repays_only_the_approved_sum(self):
        store, clock = setup()
        disburse_loan(store, "L1", SandboxMpesa(), clock)
        self.assertEqual(sum(item.principal_cents for item in loan_schedule(get_loan(store, "L1"))), 10_000_000)
