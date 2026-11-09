"""Raising invoices for parcels."""

from typing import Iterable, Optional

from ..config import INVOICE_DUE_DAYS, SECONDS_PER_DAY
from ..errors import ValidationFailed
from ..models import INVOICE_OPEN, INVOICE_VOID, Customer, Invoice, InvoiceLine, Parcel
from ..money import format_cents
from ..pricing.quote import quote_parcel
from ..store.repositories import get_customer, get_invoice, get_parcel, save_invoice


def lines_for_parcel(parcel: Parcel, customer: Optional[Customer]) -> list:
    quote = quote_parcel(parcel, customer)
    return [InvoiceLine(f"{parcel.id} {name}", cents) for name, cents in quote.lines]


def create_invoice(store, customer_id: str, parcel_ids: Iterable[str], clock) -> Invoice:
    customer = get_customer(store, customer_id)
    parcels = [get_parcel(store, parcel_id) for parcel_id in parcel_ids]
    if not parcels:
        raise ValidationFailed(["an invoice needs at least one parcel"])
    wrong = [p.id for p in parcels if p.customer_id != customer_id]
    if wrong:
        raise ValidationFailed([f"parcel {p} belongs to another customer" for p in wrong])

    lines = []
    for parcel in parcels:
        lines.extend(lines_for_parcel(parcel, customer))
    now = clock.now()
    invoice = Invoice(
        id=store.next_id("INV"),
        customer_id=customer_id,
        parcel_ids=[p.id for p in parcels],
        lines=lines,
        total_cents=sum(line.amount_cents for line in lines),
        created_at=now,
        due_at=now + INVOICE_DUE_DAYS * SECONDS_PER_DAY,
    )
    return save_invoice(store, invoice)


def void_invoice(store, invoice_id: str) -> Invoice:
    invoice = get_invoice(store, invoice_id)
    if invoice.status != INVOICE_OPEN:
        raise ValidationFailed([f"only an open invoice can be voided, this one is {invoice.status}"])
    invoice.status = INVOICE_VOID
    return save_invoice(store, invoice)


def is_overdue(invoice: Invoice, now: int) -> bool:
    return invoice.status == INVOICE_OPEN and now > invoice.due_at


def render_invoice(invoice: Invoice) -> str:
    rows = [f"Invoice {invoice.id}"]
    rows += [f"  {line.description}: {format_cents(line.amount_cents)}" for line in invoice.lines]
    rows.append(f"Total: {format_cents(invoice.total_cents)}")
    return "\n".join(rows)
