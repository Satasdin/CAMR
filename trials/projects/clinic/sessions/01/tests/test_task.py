import unittest

from clinic.clock import FixedClock, moment_at
from clinic.models import Appointment, Doctor, Patient
from clinic.reminders.dispatch import send_reminders
from clinic.reminders.sender import outbox_sender
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_appointment, save_doctor, save_patient


def world(**patient_fields):
    store = InMemoryStore()
    fields = {"phone": "+254700000001", "email": "amina@x.example"}
    fields.update(patient_fields)
    save_patient(store, Patient(id="P1", name="Amina Wanjiru", **fields))
    save_doctor(store, Doctor(id="D1", name="Dr Otieno", department="Oncology", room="B12"))
    save_appointment(store, Appointment(id="APT-7", patient_id="P1", doctor_id="D1",
                                        start_at=moment_at("2024-03-05", 10, 40), reason="chemotherapy review"))
    return store, FixedClock(moment_at("2024-03-04", 12))


def by_channel(store, channel):
    return [message for message in store.outbox if message.channel == channel]


class SmsReminders(unittest.TestCase):
    def test_sms_says_who_when_and_the_reference(self):
        store, clock = world()
        send_reminders(store, outbox_sender(store), clock)
        texts = by_channel(store, "sms")
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].to, "+254700000001")
        for piece in ("Amina", "2024-03-05", "10:40", "APT-7"):
            self.assertIn(piece, texts[0].body)

    def test_both_messages_are_counted(self):
        store, clock = world()
        self.assertEqual(send_reminders(store, outbox_sender(store), clock), 2)

    def test_no_sms_when_the_patient_does_not_want_it(self):
        store, clock = world(wants_sms=False)
        send_reminders(store, outbox_sender(store), clock)
        self.assertEqual(by_channel(store, "sms"), [])

    def test_no_sms_without_a_phone(self):
        store, clock = world(phone="")
        send_reminders(store, outbox_sender(store), clock)
        self.assertEqual(by_channel(store, "sms"), [])

    def test_email_is_unchanged(self):
        store, clock = world()
        send_reminders(store, outbox_sender(store), clock)
        self.assertEqual(len(by_channel(store, "email")), 1)
        self.assertIn("Oncology", by_channel(store, "email")[0].body)
