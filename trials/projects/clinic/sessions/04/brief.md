# Patients going to the wrong part of the building

Patients keep turning up at the wrong wing for their appointments. The SMS reminder the day before tells them when and gives a booking reference, but not where to go, so reception spends every morning redirecting people from one department to another.

Email reminders already deal with this through `location_line` in `clinic/reminders/templates.py`, which puts the doctor, the department and the room together.

Change the SMS reminder so a patient reading it knows where to go. The doctor's room (`Doctor.room`) must be in the text. Email reminders stay as they are.
