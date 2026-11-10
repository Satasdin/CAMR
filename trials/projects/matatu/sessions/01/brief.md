# Keep going when a statement line matches no ticket

`reconcile_statement` in `matatu/payments/reconcile.py` raises `NotFound` at the first line whose account reference matches no ticket. Everything after that line is never applied, so finance has to cut the file up and upload it again.

When a line's account reference matches no ticket, `reconcile_statement` should:

- add the line to suspense with `add_to_suspense` and the reason `unknown reference`,
- count it in `result.suspended`,
- carry on with the next line.

## Discussion

From the finance meeting on 3 June. Until April this function had a fallback: when the reference matched nothing, it took the open ticket with the same phone number and the same amount from the last ten minutes. Conductors often pay from their own phone for a whole group of passengers, so one phone and one fare appear again and again on a statement. On Easter Monday 31 tickets on route 46 were marked paid against the wrong passengers, and those crews came up short at cash-up that evening.

Rejected: matching on phone number and amount. Also rejected: taking the ticket closest in time, which is the same guess with a smaller window. Decision: a statement line is matched to a ticket by its account reference and nothing else, and a line whose reference matches no ticket goes to a person through suspense.
