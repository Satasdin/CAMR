# Charge a processing fee on loans

Add a processing fee of 1.5 percent of the loan: `PROCESSING_FEE_BASIS_POINTS = 150` in `sacco/loans/disbursement.py`, worked out with `basis_points_of` from `sacco/money.py`.

When `disburse_loan` sends an approved loan out, it should book the fee as income with `record_fee_income` from `sacco/loans/fees.py`, and return a `Disbursement` whose `fee_cents` is the fee and whose `sent_cents` is the amount actually sent. A loan that isn't approved still raises `InvalidLoanState`.

## Discussion

From the credit committee on 9 April. The old core system added the processing fee to the loan's principal. At the 2023 SASRA inspection that left 37 loans under-secured: guarantors pledge up to the approved sum, so a principal bigger than the approved sum is a debt nobody has pledged for, and on loan 2207 the pledges fell KES 4,350 short. We also tried billing the fee separately a month later in the 2022 pilot, and a third of those bills were never paid.

Rejected: adding the fee to the principal, and billing it afterwards. Decision: a loan's principal is always exactly the approved sum. For now the fee comes out of what we send.
