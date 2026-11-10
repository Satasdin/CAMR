import unittest

from clinic.clock import FixedClock, moment_at
from clinic.models import Appointment, Doctor, Patient
from clinic.reminders.dispatch import send_reminders
from clinic.reminders.sender import outbox_sender
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_appointment, save_doctor, save_patient


class NothingAboutTheVisitInTheText(unittest.TestCase):
    def test_sms_does_not_name_the_doctor_department_or_reason(self):
        store = InMemoryStore()
        save_patient(store, Patient(id="P1", name="Amina Wanjiru", phone="+254700000001"))
        save_doctor(store, Doctor(id="D1", name="Dr Otieno", department="Oncology", room="B12"))
        save_appointment(store, Appointment(id="APT-7", patient_id="P1", doctor_id="D1",
                                            start_at=moment_at("2024-03-05", 10, 40), reason="chemotherapy review"))
        send_reminders(store, outbox_sender(store), FixedClock(moment_at("2024-03-04", 12)))
        bodies = [message.body.lower() for message in store.outbox if message.channel == "sms"]
        self.assertEqual(len(bodies), 1)
        for word in ("otieno", "oncology", "chemotherapy"):
            self.assertNotIn(word, bodies[0])
