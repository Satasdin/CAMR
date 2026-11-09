"""Giving money back."""

from typing import Optional

from ..config import REFUND_REVIEW_LIMIT_CENTS
from ..errors import InvoiceNotOpen, RefundTooLarge, ValidationFailed
from ..models import INVOICE_PAID, INVOICE_REFUNDED, Refund
from ..store.repositories import get_invoice, save_invoice, save_refund
from .review_queue import add_to_review


def refundable_cents(invoice) -> int:
    return invoice.total_cents - invoice.refunded_cents


def request_refund(store, invoice_id: str, amount_cents: int, reason: str, gateway, clock) -> Refund:
    """Refunds at once up to the review limit. A larger refund waits for a person."""
    if amount_cents <= 0:
        raise ValidationFailed(["a refund must be more than nothing"])
    invoice = get_invoice(store, invoice_id)
    if invoice.status != INVOICE_PAID:
        raise InvoiceNotOpen(invoice_id, invoice.status)
    available = refundable_cents(invoice)
    if amount_cents > available:
        raise RefundTooLarge(amount_cents, available)

    refund = Refund(id=store.next_id("REF"), invoice_id=invoice_id, amount_cents=amount_cents, reason=reason, created_at=clock.now())
    save_refund(store, refund)
    if amount_cents > REFUND_REVIEW_LIMIT_CENTS:
        add_to_review(store, invoice_id, f"refund {refund.id} needs approval", clock)
        return refund
    return approve_refund(store, refund, gateway)


def approve_refund(store, refund: Refund, gateway, approver: Optional[str] = None) -> Refund:
    invoice = get_invoice(store, refund.invoice_id)
    gateway.refund(invoice.receipt_id, refund.amount_cents)
    refund.approved = True
    invoice.refunded_cents += refund.amount_cents
    if invoice.refunded_cents == invoice.total_cents:
        invoice.status = INVOICE_REFUNDED
    save_invoice(store, invoice)
    return save_refund(store, refund)
