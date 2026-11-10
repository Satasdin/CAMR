import unittest

from matatu.clock import FixedClock
from matatu.models import TICKET_ISSUED, TICKET_PAID, StatementLine, Ticket
from matatu.payments.reconcile import reconcile_statement
from matatu.payments.suspense import pending_suspense
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_ticket


def add_ticket(store, identifier, phone, fare=80):
    save_ticket(store, Ticket(id=identifier, trip_id="TR1", route_id="46", vehicle_id="V1", from_stage="KAW",
                              to_stage="CBD", phone=phone, fare_kes=fare, issued_at=1000))


def line(code, phone, reference, amount=80):
    return StatementLine(code=code, phone=phone, amount_kes=amount, account_ref=reference, at=2000)


class MistypedReferences(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStore()
        add_ticket(self.store, "TKT-2345AB", "+254700000001")
        add_ticket(self.store, "TKT-2345AC", "+254700000002")
        add_ticket(self.store, "TKT-2345AD", "+254700000003")

    def test_mistyped_references_end_up_on_their_ticket(self):
        lines = [line("QA1", "+254700000001", "tkt 2345ab"), line("QA2", "+254700000002", "TKT2345AC"),
                 line("QA3", "+254700000003", " Tkt-2345AD")]
        result = reconcile_statement(self.store, lines, FixedClock())
        self.assertEqual(result.matched, 3)
        self.assertEqual(pending_suspense(self.store), [])
        self.assertEqual(self.store.tickets["TKT-2345AB"].status, TICKET_PAID)
        self.assertEqual(self.store.tickets["TKT-2345AB"].payment_code, "QA1")
        self.assertEqual(self.store.tickets["TKT-2345AD"].payment_code, "QA3")

    def test_an_exact_reference_still_works(self):
        reconcile_statement(self.store, [line("QA1", "+254700000002", "TKT-2345AC")], FixedClock())
        self.assertEqual(self.store.tickets["TKT-2345AC"].status, TICKET_PAID)

    def test_a_line_for_no_ticket_goes_to_suspense(self):
        reconcile_statement(self.store, [line("QA1", "+254799999999", "HELLO", amount=75)], FixedClock())
        self.assertEqual([item.reason for item in pending_suspense(self.store)], ["unknown reference"])
        self.assertEqual(self.store.tickets["TKT-2345AB"].status, TICKET_ISSUED)
