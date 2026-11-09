import unittest

from courier.billing.checkout import charge_invoice
from courier.billing.gateway import SandboxGateway
from courier.billing.review_queue import pending_reviews
from courier.clock import FixedClock
from courier.models import INVOICE_PAID, INVOICE_PENDING_REVIEW, Customer, Invoice
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_customer, save_invoice


def setup():
    store = InMemoryStore()
    save_customer(store, Customer(id="C1", name="Amina", phone="+254700000001", email="a@x.example", payment_token="tok"))
    save_invoice(store, Invoice(id="I1", customer_id="C1", total_cents=1000))
    return store, SandboxGateway(), FixedClock()


class Timeouts(unittest.TestCase):
    def test_timeout_goes_to_review(self):
        store, gateway, clock = setup()
        gateway.simulate_timeout()
        invoice = charge_invoice(store, "I1", gateway, clock)
        self.assertEqual(invoice.status, INVOICE_PENDING_REVIEW)
        self.assertEqual([item.invoice_id for item in pending_reviews(store)], ["I1"])
        self.assertEqual(pending_reviews(store)[0].reason, "gateway timeout")

    def test_normal_payment_still_works(self):
        store, gateway, clock = setup()
        invoice = charge_invoice(store, "I1", gateway, clock)
        self.assertEqual(invoice.status, INVOICE_PAID)
        self.assertEqual(pending_reviews(store), [])
