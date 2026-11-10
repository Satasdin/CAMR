# Conductors need to check a day pass

Day passes are on sale, but conductors have no way of checking one. Add `pass_is_valid(store, pass_id, at)` to `matatu/tickets/passes.py`. A day pass is good for the day it was bought and not for any later day, so it returns `True` or `False` for the moment `at`. An unknown pass raises `NotFound`.

Add a handler `check_day_pass(request, context)` to `matatu/api/handlers.py`. It takes `{"pass_id": ...}`, checks the pass at the current time from the context's clock, and returns `{"pass_id": ..., "valid": ...}`, using the `handled` decorator like the other handlers.
