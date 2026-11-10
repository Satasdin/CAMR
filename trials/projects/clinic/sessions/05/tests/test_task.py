import unittest

from clinic.errors import ValidationFailed
from clinic.models import Patient, Prescription
from clinic.prescriptions.formulary import get_drug
from clinic.prescriptions.labels import label_text, volume_ml


def prescribed(dose_mg, code="PRN-SYR"):
    return Prescription(id="RX1", patient_id="P1", doctor_id="D1", drug_code=code, dose_mg=dose_mg)


class Graduations(unittest.TestCase):
    def test_exact_figures_are_left_alone(self):
        self.assertEqual(volume_ml(prescribed(120), get_drug("PRN-SYR")), 5.0)
        self.assertEqual(volume_ml(prescribed(180), get_drug("PRN-SYR")), 7.5)

    def test_other_figures_land_on_a_graduation(self):
        for dose in (175, 170, 130, 250):
            volume = volume_ml(prescribed(dose), get_drug("PRN-SYR"))
            self.assertEqual(volume * 2, int(volume * 2))
            self.assertLessEqual(abs(volume - dose / 24.0), 0.5)

    def test_the_bottle_shows_the_same_figure(self):
        drug = get_drug("PRN-SYR")
        prescription = prescribed(175)
        text = label_text(prescription, drug, Patient(id="P1", name="Zawadi Ochieng"))
        self.assertIn(f"{volume_ml(prescription, drug):.1f} ml", text)

    def test_tablets_are_still_refused(self):
        with self.assertRaises(ValidationFailed):
            volume_ml(prescribed(500, "MRX-TAB"), get_drug("MRX-TAB"))
