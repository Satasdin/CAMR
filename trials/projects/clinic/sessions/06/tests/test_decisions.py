import unittest

from clinic.billing.collections import chase_invoice
from clinic.billing.invoices import create_invoice
from clinic.clock import FixedClock, moment_at
from clinic.models import APPOINTMENT_COMPLETED, Appointment, Doctor, Patient
from clinic.reminders.sender import outbox_sender
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_appointment, save_doctor, save_patient


class NothingAboutTheVisitInTheText(unittest.TestCase):
    def test_sms_does_not_name_the_doctor_department_or_reason(self):
        store = InMemoryStore()
        save_patient(store, Patient(id="P1", name="Amina Wanjiru", phone="+254700000001"))
        save_doctor(store, Doctor(id="D1", name="Dr Otieno", department="Oncology", room="B12"))
        save_appointment(store, Appointment(id="APT-7", patient_id="P1", doctor_id="D1", start_at=moment_at("2024-03-05", 10, 40),
                                            reason="chemotherapy review", status=APPOINTMENT_COMPLETED))
        clock = FixedClock(moment_at("2024-04-20", 12))
        invoice = create_invoice(store, "APT-7", clock)
        body = chase_invoice(store, invoice.id, outbox_sender(store), clock).body.lower()
        for word in ("otieno", "oncology", "chemotherapy"):
            self.assertNotIn(word, body)
