# Sacco

The back office of a small savings and credit co-operative in Kenya. It keeps members
and their shares, takes deposits, lends against savings, collects repayments, charges
interest and tells members what is happening.

## Layout

- `sacco/members`: the member register, shares and identity checks.
- `sacco/savings`: savings accounts, the ledger, deposits, withdrawals and dividends.
- `sacco/loans`: products, eligibility, applications, guarantors, schedules, fees and sending money out.
- `sacco/interest`: monthly interest, accrual and late penalties.
- `sacco/repayments`: splitting a payment, applying it, arrears and recovery.
- `sacco/statements`: statements for savings and for loans.
- `sacco/notify`: message templates, delivery channels and who gets told what.
- `sacco/api`: request validation and the handlers the web layer calls.
- `sacco/reports`: portfolio and monthly figures for the board.
- `sacco/store`: an in-memory store with small repository helpers.

Money is held as whole cents. Times are whole seconds since the epoch, taken from
`sacco.clock` so tests can control them. Rates are basis points per month.

## Running the tests

    python3 -m unittest discover -s tests
