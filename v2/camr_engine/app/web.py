"""What a route is: a function of one request, registered for a method and a path.

Each screen keeps its routes in ``camr_engine/app/routes/<name>.py``, which defines ``register(routes)``:

    from camr_engine.app.web import Refused, Request, Routes

    def register(routes: Routes) -> None:
        @routes.get("/api/thing")
        def thing(req: Request) -> dict:
            return {"n": req.int("n", 0)}

A route returns what to send as JSON, or raises ``Refused(code, why)``. Any other error is sent as a 500 with its
type and message. The server has already checked the host, the origin, the content type and the launch token before
a route runs, so a route only checks its own inputs.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable


class Refused(Exception):
    """A request the route will not serve: sent as ``{"error": why}`` with ``code``."""

    def __init__(self, code: int, why: str):
        super().__init__(why)
        self.code, self.why = code, why


@dataclass
class Request:
    app: object
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    body: dict = field(default_factory=dict)

    def str(self, name: str, default: str = "", *, limit: int = 200) -> str:
        v = self.body.get(name, self.query.get(name, default))
        return default if v is None else str(v)[:limit]

    def int(self, name: str, default: int | None = None, *, lo: int | None = None, hi: int | None = None) -> int | None:
        v = self.body.get(name, self.query.get(name))
        if v is None or v == "":
            return default
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise Refused(400, f"{name} must be a whole number") from None
        if lo is not None:
            n = max(lo, n)
        return min(hi, n) if hi is not None else n

    def bool(self, name: str, default: bool = False) -> bool:
        v = self.body.get(name, self.query.get(name))
        if v is None:
            return default
        return v is True or str(v).lower() in ("1", "true", "yes", "on")


Handler = Callable[[Request], object]


class Routes:
    """Every route the server answers, by method and exact path. A path registered twice is an error, so two screens
    never answer for one path."""

    def __init__(self):
        self.table: dict[tuple[str, str], Handler] = {}
        self.owner: dict[tuple[str, str], str] = {}
        self.errors: dict[str, str] = {}  # route modules that failed to load, and why

    def add(self, method: str, path: str, fn: Handler, owner: str = "") -> Handler:
        if not path.startswith("/api/"):
            raise ValueError(f"routes live under /api/, not {path}")
        key = (method, path)
        if key in self.table:
            raise ValueError(f"{method} {path} is registered twice ({self.owner[key]} and {owner})")
        self.table[key], self.owner[key] = fn, owner
        return fn

    def get(self, path: str) -> Callable[[Handler], Handler]:
        return lambda fn: self.add("GET", path, fn, fn.__module__)

    def post(self, path: str) -> Callable[[Handler], Handler]:
        return lambda fn: self.add("POST", path, fn, fn.__module__)

    def find(self, method: str, path: str) -> Handler | None:
        return self.table.get((method, path))


_parts = threading.Lock()


def part(app: object, name: str, make: Callable[[], object]):
    """A piece of server state kept on the app (made the first time it is asked for), so routes in different
    modules share it and a stand-in app in a test gets its own."""
    with _parts:
        got = getattr(app, name, None)
        if got is None:
            got = make()
            setattr(app, name, got)
        return got
