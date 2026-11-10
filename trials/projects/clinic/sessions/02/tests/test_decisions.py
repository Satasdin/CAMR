import unittest

from clinic.clock import FixedClock
from clinic.models import Doctor, Patient
from clinic.prescriptions.dosing import paediatric_dose
from clinic.prescriptions.prescribing import prescribe_for_child
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_doctor, save_patient


class LowerAmountBetweenSteps(unittest.TestCase):
    def test_between_two_steps_goes_to_the_lower_one(self):
        self.assertEqual(paediatric_dose("ZLV-SUS", 8.0), 100)
        self.assertEqual(paediatric_dose("ZLV-SUS", 11.2), 150)

    def test_prescription_takes_the_lower_amount(self):
        store = InMemoryStore()
        save_patient(store, Patient(id="P1", name="Baraka Kamau"))
        save_doctor(store, Doctor(id="D1", name="Dr Njeri", department="Paediatrics", room="A3"))
        self.assertEqual(prescribe_for_child(store, "P1", "D1", "ZLV-SUS", 8.0, 5, FixedClock()).dose_mg, 100)
