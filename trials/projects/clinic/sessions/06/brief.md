# Chasing unpaid bills

Accounts wants an easy way to chase an unpaid bill. Add `chase_invoice(store, invoice_id, sender, clock)` in a new module, `clinic/billing/collections.py`. It sends one SMS (a `Message` with channel `sms`) to the patient's `phone` and returns that message.

The text must quote the invoice number, the amount still owed as `format_cents` prints it, and the date of the visit as `day_of` prints it. An invoice that is not open with something owing raises `ValidationFailed`, and an unknown one raises `NotFound`, as `get_invoice` does.

When accounts has sent these by hand, patients have rung back saying they could not tell what they were being billed for. These messages should stop those calls.
