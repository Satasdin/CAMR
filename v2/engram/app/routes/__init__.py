"""The server's routes, one module per screen (and one for the shell). Every module here that defines
``register(routes)`` is loaded at start, in name order. A module that fails to load is left out and named in
``/api/state`` (``route_errors``), so one screen's mistake never takes the others down.
"""

from __future__ import annotations

import importlib
import pkgutil
import traceback

from engram.app.web import Routes


def collect() -> Routes:
    routes = Routes()
    for mod in sorted(m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_")):
        try:
            module = importlib.import_module(f"{__name__}.{mod}")
            register = getattr(module, "register", None)
            if register is not None:
                register(routes)
        except Exception as e:  # noqa: BLE001 (reported, and the other screens still load)
            routes.errors[mod] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
    return routes
