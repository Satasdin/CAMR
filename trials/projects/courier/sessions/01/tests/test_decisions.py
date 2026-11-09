import unittest

from courier.billing.checkout import charge_invoice
from courier.clock import FixedClock
from courier.errors import GatewayTimeout
from courier.models import Customer, Invoice
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_customer, save_invoice


class CountingGateway:
    def __init__(self):
        self.calls = 0

    def charge(self, token, amount_cents, reference):
        self.calls += 1
        raise GatewayTimeout("no answer")

    def lookup(self, reference):
        return None


class OneChargePerAttempt(unittest.TestCase):
    def test_a_timed_out_charge_is_not_tried_again(self):
        store = InMemoryStore()
        save_customer(store, Customer(id="C1", name="Amina", phone="+254700000001", email="a@x.example", payment_token="tok"))
        save_invoice(store, Invoice(id="I1", customer_id="C1", total_cents=1000))
        gateway = CountingGateway()
        try:
            charge_invoice(store, "I1", gateway, FixedClock())
        except GatewayTimeout:
            pass
        self.assertEqual(gateway.calls, 1)
