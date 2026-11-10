# SMS reminders the day before an appointment

`send_reminders` in `clinic/reminders/dispatch.py` only sends email. Many of our patients have no email address, so the front desk spends the day before every clinic ringing them.

Make `send_reminders` also send one SMS (a `Message` with channel `sms`, to the patient's `phone`) for each appointment it reminds about, when the patient has `wants_sms` set and a phone number on file. The text must give the patient's first name, the date and time as `day_of` and `time_of` in `clinic/clock.py` print them, and the appointment id as the booking reference. The SMS counts towards the number `send_reminders` returns, as an email does. Email reminders carry on unchanged.

## Discussion

From the records committee on 4 June. The SMS gateway we used until last year printed the doctor and the department, for example "Dr Mwangi, Oncology, Tuesday 10:40". In April the husband of one patient read such a message on the phone they share, and learned of her diagnosis before she had told him. She complained to the county data office and the clinic paid a settlement. A front desk survey in May found that about one in three phone numbers on file belongs to a handset shared with relatives.

Rejected: an opt-in box for detailed texts, because reception does not ask every patient and the default is wrong for exactly the people it hurts. Rejected: shortening departments to codes such as ONC, because at the pilot clinic relatives had worked the codes out within weeks. Email stays as it is, since an inbox belongs to one person.

Decision: no SMS to a patient, about anything, ever names the doctor, the department or the reason for the visit.
