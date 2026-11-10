import unittest

from matatu.clock import FixedClock
from matatu.models import TICKET_ISSUED, TICKET_PAID, StatementLine, Ticket
from matatu.payments.reconcile import reconcile_statement
from matatu.payments.suspense import pending_suspense
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_ticket


def ticket(identifier, phone, fare=80):
    return Ticket(id=identifier, trip_id="TR1", route_id="46", vehicle_id="V1", from_stage="KAW", to_stage="CBD",
                  phone=phone, fare_kes=fare, issued_at=1000)


def line(code, phone, amount, reference):
    return StatementLine(code=code, phone=phone, amount_kes=amount, account_ref=reference, at=2000)


class UnknownReferences(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStore()
        save_ticket(self.store, ticket("TKT-2345AB", "+254700000001"))
        save_ticket(self.store, ticket("TKT-2345AC", "+254700000002"))

    def test_unknown_reference_goes_to_suspense(self):
        result = reconcile_statement(self.store, [line("QA1", "+254799999999", 70, "NOTHING")], FixedClock())
        self.assertEqual(result.suspended, 1)
        self.assertEqual([item.line_code for item in pending_suspense(self.store)], ["QA1"])
        self.assertEqual(pending_suspense(self.store)[0].reason, "unknown reference")

    def test_the_rest_of_the_statement_is_applied(self):
        lines = [line("QA1", "+254799999999", 70, "NOTHING"), line("QA2", "+254700000002", 80, "TKT-2345AC")]
        result = reconcile_statement(self.store, lines, FixedClock())
        self.assertEqual(result.matched, 1)
        self.assertEqual(self.store.tickets["TKT-2345AC"].status, TICKET_PAID)
        self.assertEqual(self.store.tickets["TKT-2345AC"].payment_code, "QA2")
        self.assertEqual(self.store.tickets["TKT-2345AB"].status, TICKET_ISSUED)

    def test_wrong_amount_still_goes_to_suspense(self):
        reconcile_statement(self.store, [line("QA3", "+254700000001", 70, "TKT-2345AB")], FixedClock())
        self.assertEqual(pending_suspense(self.store)[0].reason, "wrong amount")
