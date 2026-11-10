# Day-close report for the treasurer

Add `matatu/reports/day_close.py` with `day_close(store, day)`, where `day` is a string like `2023-11-15`. It returns a dictionary with these keys:

- `day`: the day asked for,
- `tickets`: how many tickets with the status `paid` belong to that day,
- `takings_kes`: the total of their fares,
- `by_route`: a dictionary of route id to that route's takings.

Tickets are placed by their `issued_at`. A day with nothing on it returns zeros and an empty `by_route`.

Add a handler `day_close_report(request, context)` to `matatu/api/handlers.py`. It takes `{"day": ...}` and returns the dictionary from `day_close`, using the `handled` decorator like the other handlers. A request with no `day` gets the usual `invalid` error.

## Discussion

Talked this through with the treasurer and the Eastlands depot on 18 September. Our first draft counted calendar days. The night service on routes 58 and 19C runs until about 02:30, and those crews hand in one envelope at 03:00 for the whole night. Cutting at midnight split one night's takings over two reports, so over the Madaraka weekend Saturday looked short, Sunday looked long, and the treasurer sent both back.

Decision: a day in this business is an operating day, running from 03:00 to 03:00 Nairobi time, so a ticket issued at 01:30 on the 16th belongs to the 15th. Everything built from now on that asks which day something happened on uses the operating day. Only the existing `figures_for` stays on calendar days, since finance compares it line by line with the provider's statement, which runs midnight to midnight.

Rejected: calendar days, and rejected a different cut-over hour per route, since a crew can change routes during a night.
