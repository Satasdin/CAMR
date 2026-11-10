import unittest

from clinic.clock import FixedClock
from clinic.models import Patient, Vitals
from clinic.store.memory import InMemoryStore
from clinic.store.repositories import save_patient
from clinic.triage.levels import LEVEL_URGENT
from clinic.triage.queue import admit
from clinic.triage.scoring import score_vitals


class Oxygen(unittest.TestCase):
    def test_below_90(self):
        self.assertEqual(score_vitals(Vitals(spo2=89)).points("oxygen"), 3)

    def test_edges_of_the_middle_band(self):
        self.assertEqual(score_vitals(Vitals(spo2=90)).points("oxygen"), 2)
        self.assertEqual(score_vitals(Vitals(spo2=93)).points("oxygen"), 2)

    def test_no_line_when_normal(self):
        self.assertNotIn("oxygen", [name for name, _ in score_vitals(Vitals(spo2=94)).lines])

    def test_counts_towards_the_total(self):
        self.assertEqual(score_vitals(Vitals(spo2=89)).total, score_vitals(Vitals(spo2=98)).total + 3)

    def test_changes_the_level_in_the_queue(self):
        store = InMemoryStore()
        save_patient(store, Patient(id="P1", name="Zawadi Ochieng"))
        self.assertEqual(admit(store, "P1", Vitals(spo2=85), FixedClock()).level, LEVEL_URGENT)
