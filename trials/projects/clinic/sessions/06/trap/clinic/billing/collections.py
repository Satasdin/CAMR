"""Asking patients to pay what they owe."""

from ..clock import day_of
from ..config import DEFAULT_SETTINGS, Settings
from ..errors import ValidationFailed
from ..models import INVOICE_OPEN, Message
from ..money import format_cents
from ..store.repositories import get_appointment, get_invoice, get_patient
from .invoices import outstanding_cents


def chase_invoice(store, invoice_id: str, sender, clock, settings: Settings = DEFAULT_SETTINGS) -> Message:
    """Sends the patient one SMS about an unpaid invoice and returns it."""
    invoice = get_invoice(store, invoice_id)
    owed = outstanding_cents(invoice)
    if invoice.status != INVOICE_OPEN or owed <= 0:
        raise ValidationFailed([f"invoice {invoice_id} has nothing to chase"])
    patient = get_patient(store, invoice.patient_id)
    appointment = get_appointment(store, invoice.appointment_id)
    body = (f"{patient.first_name}, invoice {invoice.id} for your visit to {settings.clinic_name} on "
            f"{day_of(appointment.start_at)} has {format_cents(owed)} unpaid "
            f"({', '.join(line.description for line in invoice.lines)}). "
            f"Questions? Call {settings.accounts_phone}.")
    message = Message(channel="sms", to=patient.phone, body=body, sent_at=clock.now())
    sender.send(message)
    return message
