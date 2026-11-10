# Tellers need to correct a mistyped deposit

Tellers keep mistyping the amount when they post a deposit, and the ledger balance and the member's printed statement are then wrong until someone at head office fixes the ledger by hand. A deposit of KES 500 posted as KES 5,000 is the usual story.

Add `correct_deposit(store, entry_id, right_amount_cents, clock)` to `sacco/savings/deposits.py`. It fixes the posted deposit so that the ledger balance and the member's statement show the amount that was really paid, and returns the account's new balance in cents. Only a deposit can be corrected; a ledger entry of any other kind, or an amount that is not positive, raises `ValidationFailed`. An unknown entry raises `NotFound`.
