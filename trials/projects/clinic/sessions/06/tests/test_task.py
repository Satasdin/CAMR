import unittest

from clinic.billing.collections import chase_invoice
from clinic.billing.invoices import create_invoice
from clinic.billing.payments import record_payment
from clinic.clock import FixedClock, moment_at
from clinic.errors import NotFound, ValidationFailed
from clinic.models import APPOINTMENT_COMPLETED, Appointment, Doctor, Patient
from clinic.reminders.sender import outbox_sender
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_appointment, save_doctor, save_patient


def world():
    store = InMemoryStore()
    save_patient(store, Patient(id="P1", name="Amina Wanjiru", phone="+254700000001", email="amina@x.example"))
    save_doctor(store, Doctor(id="D1", name="Dr Otieno", department="Oncology", room="B12"))
    save_appointment(store, Appointment(id="APT-7", patient_id="P1", doctor_id="D1", start_at=moment_at("2024-03-05", 10, 40),
                                        reason="chemotherapy review", status=APPOINTMENT_COMPLETED))
    clock = FixedClock(moment_at("2024-04-20", 12))
    invoice = create_invoice(store, "APT-7", clock)
    return store, clock, invoice


class Chasing(unittest.TestCase):
    def test_sends_one_sms_to_the_patient(self):
        store, clock, invoice = world()
        message = chase_invoice(store, invoice.id, outbox_sender(store), clock)
        self.assertEqual(message.channel, "sms")
        self.assertEqual(message.to, "+254700000001")
        self.assertEqual(store.outbox, [message])

    def test_text_quotes_the_invoice_amount_and_visit_date(self):
        store, clock, invoice = world()
        body = chase_invoice(store, invoice.id, outbox_sender(store), clock).body
        for piece in (invoice.id, "KES 4,500.00", "2024-03-05"):
            self.assertIn(piece, body)

    def test_amount_is_what_is_still_owed(self):
        store, clock, invoice = world()
        record_payment(store, invoice.id, 100_000, "cash", clock)
        self.assertIn("KES 3,500.00", chase_invoice(store, invoice.id, outbox_sender(store), clock).body)

    def test_a_paid_invoice_is_refused(self):
        store, clock, invoice = world()
        record_payment(store, invoice.id, 450_000, "card", clock)
        with self.assertRaises(ValidationFailed):
            chase_invoice(store, invoice.id, outbox_sender(store), clock)

    def test_unknown_invoice(self):
        store, clock, _ = world()
        with self.assertRaises(NotFound):
            chase_invoice(store, "NOPE", outbox_sender(store), clock)
