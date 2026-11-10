# Owner payouts

Vehicle owners are paid per date. Add `owner_payout(store, owner_id, date)` to `matatu/fleet/owners.py`, where `date` is a string like `2023-11-15`. It returns a dictionary with these keys:

- `owner_id` and `date`: as given,
- `gross_kes`: the fares of the `paid` tickets on the owner's vehicles for that date, placed by each ticket's `issued_at`,
- `levy_kes`: the SACCO levy, `SACCO_LEVY_PERCENT` of the gross, using `percent_of`,
- `net_kes`: gross minus levy.

An unknown owner raises `NotFound`.
