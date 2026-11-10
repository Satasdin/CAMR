# Matatu

The back office of a Nairobi minibus operator. It keeps the routes and stages, works
out fares, sells tickets, tracks vehicles and crews, matches the mobile-money statement
to tickets and prepares the daily figures.

## Layout

- `matatu/routes`: stages and the order they come in along a route.
- `matatu/fares`: distance bands, peak hours, extras and rider discounts, combined into a quote.
- `matatu/tickets`: selling tickets, boarding, refunds and day passes.
- `matatu/fleet`: vehicles, inspections, fuel and vehicle owners.
- `matatu/crews`: drivers and conductors, shifts and commission.
- `matatu/payments`: the mobile-money statement, matching lines to tickets, suspense and the provider.
- `matatu/reports`: figures for finance and the routes table.
- `matatu/notify`: message templates and delivery channels.
- `matatu/api`: request validation and the handlers the web layer calls.
- `matatu/store`: an in-memory store with small repository helpers.

Money is held as whole Kenya shillings. Times are whole seconds since the epoch, taken from
`matatu.clock` so tests can control them.

## Running the tests

    python3 -m unittest discover -s tests
