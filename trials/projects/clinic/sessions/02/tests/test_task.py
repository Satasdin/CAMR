import unittest

from clinic.clock import FixedClock
from clinic.errors import AllergyConflict, NotFound, ValidationFailed
from clinic.models import Doctor, Patient
from clinic.prescriptions.dosing import paediatric_dose
from clinic.prescriptions.prescribing import prescribe_for_child
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_doctor, save_patient


class Dose(unittest.TestCase):
    def test_exact_amount(self):
        self.assertEqual(paediatric_dose("ZLV-SUS", 10.0), 150)

    def test_held_at_the_maximum(self):
        self.assertEqual(paediatric_dose("ZLV-SUS", 60.0), 500)

    def test_result_is_a_whole_number_of_steps(self):
        self.assertEqual(paediatric_dose("ZLV-SUS", 10.4), 150)

    def test_bad_weight(self):
        for weight in (0, -3):
            with self.assertRaises(ValidationFailed):
                paediatric_dose("ZLV-SUS", weight)

    def test_unknown_drug(self):
        with self.assertRaises(NotFound):
            paediatric_dose("NOPE", 10.0)


class Prescribing(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStore()
        save_patient(self.store, Patient(id="P1", name="Baraka Kamau", allergies=["pirenol"]))
        save_doctor(self.store, Doctor(id="D1", name="Dr Njeri", department="Paediatrics", room="A3"))

    def test_prescription_carries_the_dose(self):
        prescription = prescribe_for_child(self.store, "P1", "D1", "ZLV-SUS", 10.0, 5, FixedClock())
        self.assertEqual(prescription.dose_mg, 150)
        self.assertEqual(prescription.days, 5)
        self.assertIn(prescription.id, self.store.prescriptions)

    def test_allergy_check_still_applies(self):
        with self.assertRaises(AllergyConflict):
            prescribe_for_child(self.store, "P1", "D1", "PRN-SYR", 10.0, 5, FixedClock())
