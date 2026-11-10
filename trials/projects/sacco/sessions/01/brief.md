# Undo a mistaken posting

Tellers have no way to undo a deposit or withdrawal that was posted by mistake.

Add `sacco/savings/reversals.py` with `reverse_entry(store, entry_id, reason, clock)`. It undoes the ledger entry so that the account's balance is back to what it was without that entry, and returns the account's new balance in cents. An unknown entry raises `NotFound`, as `find_entry` in `sacco/savings/ledger.py` does. Reversing the same entry a second time raises `AlreadyReversed`.

Add a handler `reverse_posting(request, context)` to `sacco/api/handlers.py`. It takes `{"entry_id": ..., "reason": ...}` and returns `{"entry_id": ..., "balance_cents": ...}`, using the `handled` decorator like the other handlers.

## Discussion

From the audit committee on 18 June. For years tellers fixed a mistyped or wrong posting by deleting the ledger line and entering it again. At the 2023 SASRA inspection the inspector found 214 deposits with no ledger line for money we had clearly received, and a member walked in with a printed statement showing a deposit the ledger no longer held. Members keep their printed statements, and the auditors tick statements against the ledger line by line.

The treasurer wanted to keep the line but set a `reversed` flag on it and leave it out of balances. Rejected: a flag changes what an old line means after the fact, so an old printed statement and the ledger disagree with no line to explain why. Deleting the line is rejected for the reasons above.

Decision: a reversal posts a new ledger line for the opposite amount, and the original line is never changed or removed. Both lines stay on the statement.
