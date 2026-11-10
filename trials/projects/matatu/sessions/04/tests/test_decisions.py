import unittest

from matatu.clock import FixedClock
from matatu.models import TICKET_ISSUED, TICKET_PAID, StatementLine, Ticket
from matatu.payments.reconcile import reconcile_statement
from matatu.payments.suspense import pending_suspense
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_ticket


def store_with_tickets():
    store = InMemoryStore()
    for identifier, phone in (("TKT-2345AB", "+254700000001"), ("TKT-2345AC", "+254700000002")):
        save_ticket(store, Ticket(id=identifier, trip_id="TR1", route_id="46", vehicle_id="V1", from_stage="KAW",
                                  to_stage="CBD", phone=phone, fare_kes=80, issued_at=1000))
    return store


class MatchedByReferenceOnly(unittest.TestCase):
    def test_phone_and_amount_alone_do_not_make_a_match(self):
        store = store_with_tickets()
        line = StatementLine(code="QA1", phone="+254700000001", amount_kes=80, account_ref="FARE", at=1100)
        reconcile_statement(store, [line], FixedClock())
        self.assertEqual(store.tickets["TKT-2345AB"].status, TICKET_ISSUED)
        self.assertEqual([item.reason for item in pending_suspense(store)], ["unknown reference"])

    def test_a_group_payment_lands_on_the_ticket_it_names(self):
        store = store_with_tickets()
        line = StatementLine(code="QA1", phone="+254700000002", amount_kes=80, account_ref="tkt 2345ab", at=1100)
        reconcile_statement(store, [line], FixedClock())
        self.assertEqual(store.tickets["TKT-2345AB"].status, TICKET_PAID)
        self.assertEqual(store.tickets["TKT-2345AC"].status, TICKET_ISSUED)
