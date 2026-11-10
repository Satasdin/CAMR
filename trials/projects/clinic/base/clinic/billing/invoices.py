"""Raising invoices for visits."""

from ..config import INVOICE_DUE_DAYS, SECONDS_PER_DAY
from ..errors import ValidationFailed
from ..models import INVOICE_OPEN, INVOICE_VOID, Invoice, InvoiceLine
from ..money import format_cents
from ..store.repositories import get_appointment, get_doctor, get_invoice, save_invoice
from .tariffs import lines_for


def create_invoice(store, appointment_id: str, clock) -> Invoice:
    appointment = get_appointment(store, appointment_id)
    doctor = get_doctor(store, appointment.doctor_id)
    lines = [InvoiceLine(description, cents) for description, cents in lines_for(appointment, doctor)]
    if not lines:
        raise ValidationFailed(["there is nothing to bill for this appointment"])
    now = clock.now()
    invoice = Invoice(id=store.next_id("INV"), patient_id=appointment.patient_id, appointment_id=appointment_id,
                      lines=lines, total_cents=sum(line.amount_cents for line in lines),
                      created_at=now, due_at=now + INVOICE_DUE_DAYS * SECONDS_PER_DAY)
    return save_invoice(store, invoice)


def outstanding_cents(invoice: Invoice) -> int:
    return invoice.total_cents - invoice.paid_cents


def void_invoice(store, invoice_id: str) -> Invoice:
    invoice = get_invoice(store, invoice_id)
    if invoice.status != INVOICE_OPEN or invoice.paid_cents:
        raise ValidationFailed([f"invoice {invoice_id} cannot be voided"])
    invoice.status = INVOICE_VOID
    return save_invoice(store, invoice)


def is_overdue(invoice: Invoice, now: int) -> bool:
    return invoice.status == INVOICE_OPEN and now > invoice.due_at


def render_invoice(invoice: Invoice) -> str:
    rows = [f"Invoice {invoice.id}"]
    rows += [f"  {line.description}: {format_cents(line.amount_cents)}" for line in invoice.lines]
    rows.append(f"Total: {format_cents(invoice.total_cents)}")
    rows.append(f"Outstanding: {format_cents(outstanding_cents(invoice))}")
    return "\n".join(rows)
