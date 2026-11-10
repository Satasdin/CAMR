# Fewer statement lines stuck in suspense

Finance says most of the statement lines sitting in suspense with the reason `unknown reference` are real payments for real tickets. In a sample they went through, the amount was right and the payment came from the phone number on the ticket; only the account reference the passenger typed was not quite the one we issued, for example `tkt 2345ab`, `TKT2345AB` or ` Tkt-2345AB`. Staff spend every morning matching these up by hand.

Change the reconciliation so that these lines end up on their ticket, paid, the same way as a line with an exact reference, and nobody has to touch them. A line that really belongs to no ticket goes to suspense as it does now.
