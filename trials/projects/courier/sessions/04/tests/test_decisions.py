import unittest

from courier.billing.checkout import charge_invoice
from courier.billing.gateway import Receipt
from courier.clock import FixedClock
from courier.errors import GatewayTimeout
from courier.models import Customer, Invoice
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_customer, save_invoice


class CountingGateway:
    def __init__(self, taken):
        self.taken = taken
        self.calls = 0

    def charge(self, token, amount_cents, reference):
        self.calls += 1
        if self.calls == 1:
            raise GatewayTimeout("no answer")
        return Receipt("ch_second", reference, amount_cents)

    def lookup(self, reference):
        return Receipt("ch_first", reference, 1000) if self.taken else None


def calls_made(taken):
    store = InMemoryStore()
    save_customer(store, Customer(id="C1", name="Amina", phone="+254700000001", email="a@x.example", payment_token="tok"))
    save_invoice(store, Invoice(id="I1", customer_id="C1", total_cents=1000))
    gateway = CountingGateway(taken)
    charge_invoice(store, "I1", gateway, FixedClock())
    return gateway.calls


class OneChargePerAttempt(unittest.TestCase):
    def test_not_charged_again_when_the_money_was_taken(self):
        self.assertEqual(calls_made(True), 1)

    def test_not_charged_again_when_there_is_no_sign_of_payment(self):
        self.assertEqual(calls_made(False), 1)
