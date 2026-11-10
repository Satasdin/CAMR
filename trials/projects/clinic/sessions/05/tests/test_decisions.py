import unittest

from clinic.models import Prescription
from clinic.prescriptions.formulary import get_drug
from clinic.prescriptions.labels import volume_ml


def volume(dose_mg):
    prescription = Prescription(id="RX1", patient_id="P1", doctor_id="D1", drug_code="PRN-SYR", dose_mg=dose_mg)
    return volume_ml(prescription, get_drug("PRN-SYR"))


class LowerAmountBetweenSteps(unittest.TestCase):
    def test_between_two_graduations_goes_to_the_lower_one(self):
        self.assertEqual(volume(175), 7.0)
        self.assertEqual(volume(190), 7.5)
