# Courier

A small parcel delivery back end. It quotes prices, takes parcels, bills customers,
tracks deliveries and tells customers what is happening.

## Layout

- `courier/pricing`: zones, rates, surcharges and discounts, combined into a quote.
- `courier/billing`: invoices, the payment gateway, checkout, refunds and the review queue.
- `courier/tracking`: delivery status changes, tracking events and arrival estimates.
- `courier/notify`: message templates, delivery channels and who gets told what.
- `courier/accounts`: customers and their preferences.
- `courier/api`: request validation and the handlers the web layer calls.
- `courier/reports`: daily and weekly figures for finance.
- `courier/store`: an in-memory store with small repository helpers.

Money is held as whole cents. Times are whole seconds since the epoch, taken from
`courier.clock` so tests can control them.

## Running the tests

    python3 -m unittest discover -s tests
