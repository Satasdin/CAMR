"""Recording what patients pay."""

from ..errors import InvoiceNotOpen, PaymentTooLarge, ValidationFailed
from ..models import INVOICE_OPEN, INVOICE_PAID, Invoice, Payment
from ..store.repositories import get_invoice, save_invoice, save_payment
from .invoices import outstanding_cents

METHODS = ("cash", "card", "mobile_money")


def record_payment(store, invoice_id: str, amount_cents: int, method: str, clock) -> Invoice:
    invoice = get_invoice(store, invoice_id)
    if invoice.status != INVOICE_OPEN:
        raise InvoiceNotOpen(invoice_id, invoice.status)
    if method not in METHODS:
        raise ValidationFailed([f"unknown payment method: {method}"])
    if amount_cents <= 0:
        raise ValidationFailed(["a payment must be more than zero"])
    owed = outstanding_cents(invoice)
    if amount_cents > owed:
        raise PaymentTooLarge(amount_cents, owed)
    save_payment(store, Payment(id=store.next_id("PAY"), invoice_id=invoice_id, amount_cents=amount_cents,
                                method=method, at=clock.now()))
    invoice.paid_cents += amount_cents
    if outstanding_cents(invoice) == 0:
        invoice.status = INVOICE_PAID
    return save_invoice(store, invoice)
