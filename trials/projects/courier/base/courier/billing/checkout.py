"""Taking payment for an invoice."""

from ..errors import GatewayDeclined, InvoiceNotOpen, PaymentDeclined
from ..models import INVOICE_OPEN, INVOICE_PAID, Invoice
from ..store.repositories import get_customer, get_invoice, save_invoice


def _mark_paid(store, invoice: Invoice, receipt, clock) -> Invoice:
    invoice.status = INVOICE_PAID
    invoice.paid_at = clock.now()
    invoice.receipt_id = receipt.charge_id
    return save_invoice(store, invoice)


def charge_invoice(store, invoice_id: str, gateway, clock) -> Invoice:
    """Charges the customer's saved payment method for one invoice."""
    invoice = get_invoice(store, invoice_id)
    if invoice.status != INVOICE_OPEN:
        raise InvoiceNotOpen(invoice_id, invoice.status)
    customer = get_customer(store, invoice.customer_id)
    try:
        receipt = gateway.charge(customer.payment_token, invoice.total_cents, reference=invoice.id)
    except GatewayDeclined as declined:
        raise PaymentDeclined(declined.reason) from declined
    return _mark_paid(store, invoice, receipt, clock)
