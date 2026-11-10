# Weight-based doses for children

Add `paediatric_dose(drug_code, weight_kg)` to `clinic/prescriptions/dosing.py`. Multiply the drug's `mg_per_kg` by the weight, hold the result at the drug's `max_single_mg`, and return an amount that is a whole number of the drug's `step_mg`, the smallest quantity pharmacy can measure out for that drug. A weight of zero or less raises `ValidationFailed`. An unknown drug raises `NotFound`, as `get_drug` does.

Add `prescribe_for_child(store, patient_id, doctor_id, drug_code, weight_kg, days, clock)` to `clinic/prescriptions/prescribing.py`. It works out the dose with `paediatric_dose` and goes through `prescribe`, so the allergy and interaction checks still apply.

## Discussion

From the medicines committee on 9 August. The spreadsheet this replaces went to the nearest step. In the July audit a child of 8 kg on Zolvicin came out at 125 mg against a worked-out 120 mg, which is over the 15 mg per kg the committee sets as a ceiling for that drug, and the audit found the same thing on roughly half the children's prescriptions it sampled.

Rejected: the nearest step, for that reason. Rejected: going up to the next step so that no child is under-treated, because a low dose is corrected at the review visit and a high one is not. Rejected: leaving the exact amount, because pharmacy cannot measure it.

Decision: whenever an amount of medicine falls between two quantities that can be measured, it goes to the lower one. That holds for every unit and every drug, wherever in the system such an amount is worked out.
