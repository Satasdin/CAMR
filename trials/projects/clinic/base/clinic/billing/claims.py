"""Insurance claims against invoices."""

from typing import List

from ..config import insurer
from ..errors import InvoiceNotOpen, ValidationFailed
from ..models import CLAIM_REJECTED, CLAIM_SETTLED, CLAIM_SUBMITTED, INVOICE_OPEN, Claim
from ..money import percent_of
from ..store.repositories import get_invoice, save_claim
from .invoices import outstanding_cents


def covered_cents(total_cents: int, insurer_code: str) -> int:
    return percent_of(total_cents, insurer(insurer_code).cover_percent)


def open_claim(store, invoice_id: str, insurer_code: str, clock) -> Claim:
    invoice = get_invoice(store, invoice_id)
    if invoice.status != INVOICE_OPEN:
        raise InvoiceNotOpen(invoice_id, invoice.status)
    amount = covered_cents(outstanding_cents(invoice), insurer_code)
    claim = Claim(id=store.next_id("CLM"), invoice_id=invoice_id, insurer=insurer_code, covered_cents=amount,
                  created_at=clock.now())
    return save_claim(store, claim)


def settle_claim(store, claim: Claim) -> Claim:
    if claim.status != CLAIM_SUBMITTED:
        raise ValidationFailed([f"claim {claim.id} is {claim.status}"])
    claim.status = CLAIM_SETTLED
    return save_claim(store, claim)


def reject_claim(store, claim: Claim) -> Claim:
    if claim.status != CLAIM_SUBMITTED:
        raise ValidationFailed([f"claim {claim.id} is {claim.status}"])
    claim.status = CLAIM_REJECTED
    return save_claim(store, claim)


def claims_for(store, invoice_id: str) -> List[Claim]:
    return [c for c in store.claims.values() if c.invoice_id == invoice_id]
