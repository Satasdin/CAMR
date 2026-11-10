# Clinic

A small outpatient clinic back end. It registers patients, books appointments against
doctors' schedules, triages walk-ins, writes prescriptions, bills visits and reminds
patients what is coming up.

## Layout

- `clinic/patients`: the patient register, allergies and contact preferences.
- `clinic/scheduling`: rosters, open slots, appointments, cancellations and the waitlist.
- `clinic/triage`: scoring vital signs, urgency levels and the walk-in queue.
- `clinic/prescriptions`: the formulary, doses, prescribing, refills, interactions and labels.
- `clinic/billing`: tariffs, invoices, payments, insurance claims and statements.
- `clinic/reminders`: message templates, delivery and who gets reminded about what.
- `clinic/api`: request validation and the handlers the web layer calls.
- `clinic/reports`: daily and weekly figures for management.
- `clinic/store`: an in-memory store with small repository helpers.

Money is held as whole cents. Times are whole seconds since the epoch, taken from
`clinic.clock` so tests can control them.

## Running the tests

    python3 -m unittest discover -s tests
