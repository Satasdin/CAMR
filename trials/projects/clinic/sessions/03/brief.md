# Oxygen in the triage score

`score_vitals` in `clinic/triage/scoring.py` scores temperature, heart rate, breathing and blood pressure. `Vitals` has an `spo2` field, but nothing uses it.

Add it to the score as a line named `oxygen`: 3 points below 90, 2 points from 90 to 93, and no line at all from 94 up.
