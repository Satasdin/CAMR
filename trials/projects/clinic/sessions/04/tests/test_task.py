import unittest

from clinic.clock import FixedClock, moment_at
from clinic.models import Appointment, Doctor, Patient
from clinic.reminders.dispatch import send_reminders
from clinic.reminders.sender import outbox_sender
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_appointment, save_doctor, save_patient


def messages():
    store = InMemoryStore()
    save_patient(store, Patient(id="P1", name="Amina Wanjiru", phone="+254700000001", email="amina@x.example"))
    save_doctor(store, Doctor(id="D1", name="Dr Otieno", department="Oncology", room="B12"))
    save_appointment(store, Appointment(id="APT-7", patient_id="P1", doctor_id="D1",
                                        start_at=moment_at("2024-03-05", 10, 40), reason="chemotherapy review"))
    send_reminders(store, outbox_sender(store), FixedClock(moment_at("2024-03-04", 12)))
    return {message.channel: message for message in store.outbox}


class WhereToGo(unittest.TestCase):
    def test_sms_gives_the_room(self):
        self.assertIn("B12", messages()["sms"].body)

    def test_sms_still_gives_when_and_the_reference(self):
        body = messages()["sms"].body
        for piece in ("Amina", "2024-03-05", "10:40", "APT-7"):
            self.assertIn(piece, body)

    def test_email_is_unchanged(self):
        self.assertIn("Dr Otieno, Oncology, room B12", messages()["email"].body)
