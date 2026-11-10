import unittest

from matatu.clock import FixedClock
from matatu.models import TICKET_ISSUED, StatementLine, Ticket
from matatu.payments.reconcile import reconcile_statement
from matatu.payments.suspense import pending_suspense
from matatu.store.memory import InMemoryStore
from matatu.store.repositories import save_ticket


class MatchedByReferenceOnly(unittest.TestCase):
    def test_same_phone_and_amount_does_not_make_a_match(self):
        store = InMemoryStore()
        save_ticket(store, Ticket(id="TKT-2345AB", trip_id="TR1", route_id="46", vehicle_id="V1", from_stage="KAW",
                                  to_stage="CBD", phone="+254700000001", fare_kes=80, issued_at=1000))
        line = StatementLine(code="QA1", phone="+254700000001", amount_kes=80, account_ref="NOTHING", at=1100)
        reconcile_statement(store, [line], FixedClock())
        self.assertEqual(store.tickets["TKT-2345AB"].status, TICKET_ISSUED)
        self.assertEqual([item.reason for item in pending_suspense(store)], ["unknown reference"])
