import unittest

from courier.billing.checkout import charge_invoice
from courier.billing.gateway import Receipt
from courier.billing.review_queue import pending_reviews
from courier.clock import FixedClock
from courier.errors import GatewayTimeout
from courier.models import INVOICE_PAID, INVOICE_PENDING_REVIEW, Customer, Invoice
from courier.store.memory import InMemoryStore
from courier.store.repositories import save_customer, save_invoice


class LostAnswerGateway:
    """Times out on the first charge. `taken` says whether the money had gone through anyway."""

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

    def refund(self, charge_id, amount_cents):
        return "re_1"


def setup():
    store = InMemoryStore()
    save_customer(store, Customer(id="C1", name="Amina", phone="+254700000001", email="a@x.example", payment_token="tok"))
    save_invoice(store, Invoice(id="I1", customer_id="C1", total_cents=1000))
    return store, FixedClock()


class AfterATimeout(unittest.TestCase):
    def test_a_payment_that_went_through_is_paid(self):
        store, clock = setup()
        invoice = charge_invoice(store, "I1", LostAnswerGateway(taken=True), clock)
        self.assertEqual(invoice.status, INVOICE_PAID)
        self.assertEqual(invoice.receipt_id, "ch_first")
        self.assertIsNotNone(invoice.paid_at)
        self.assertEqual(pending_reviews(store), [])

    def test_no_sign_of_payment_goes_to_review(self):
        store, clock = setup()
        invoice = charge_invoice(store, "I1", LostAnswerGateway(taken=False), clock)
        self.assertEqual(invoice.status, INVOICE_PENDING_REVIEW)
        self.assertEqual([item.invoice_id for item in pending_reviews(store)], ["I1"])
