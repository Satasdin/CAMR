"""The shell's routes: what the top strip and every screen read.

- ``GET /api/state``: the app's own state, plus the loaded model, the measuring flag, the tiers and reaches when the
  app has them, whether this is a fixture, and route modules that failed to load;
- ``GET /api/sys``: RAM in use (total, this process, pressure) and the disk, read now;
- ``GET /api/events?after=N`` and ``GET /api/metrics?after=N``: new lines of ``events.jsonl`` and ``metrics.jsonl``
  after line N (at most 500; ``limit`` asks for fewer, ``tail=K`` without ``after`` gives the last K), as
  ``{next, total, events}``, each line with its number ``i``;
- ``GET /api/metrics/summary``: medians and 90th percentiles over every metrics record.
"""

from __future__ import annotations

import time
from pathlib import Path

from camr_engine.app.web import Request, Routes, part


def _paths(app) -> dict:
    try:
        return app.paths() if hasattr(app, "paths") else {}
    except Exception:  # noqa: BLE001 (a stand-in app may have no memory)
        return {}


def _tail(app, kind: str):
    from camr_engine.app.tail import Tail

    path = _paths(app).get(kind)
    if path is None:
        return None
    tails = part(app, "_tails", dict)
    key = (kind, str(path))
    if key not in tails:
        tails[key] = Tail(Path(path))
    return tails[key]


def model_line(app) -> dict | None:
    """The model the strip shows: the one picked on the Models screen, else the memory's reader."""
    runtime = getattr(app, "models", None)
    if runtime is None:
        return None
    s = runtime.state()
    slot = s.get("picked") or s.get("memory")
    job = s.get("job")
    return {"repo": slot.get("repo") if slot else None, "loading": job["repo"] if job and job["state"] == "loading"
            else None}


def register(routes: Routes) -> None:
    @routes.get("/api/state")
    def state(req: Request) -> dict:
        from camr_engine.app.measuring import active

        app = req.app
        out = dict(app.state()) if hasattr(app, "state") else {}
        out["measuring"] = active()
        out["model"] = model_line(app)
        out["fixture"] = bool(getattr(app, "fixture", False))
        out["route_errors"] = getattr(app, "route_errors", {})
        memory = getattr(app, "memory", None)
        tiers = getattr(memory, "tiers", None)
        if tiers is not None:
            out["tiers"] = tiers.state()
        session = getattr(app, "session", None)
        if session is not None and hasattr(session, "state"):
            out["reaches"] = session.state().get("reaches")
        return out

    @routes.get("/api/sys")
    def sys_now(req: Request) -> dict:
        from camr_engine import hardware

        kept = part(req.app, "_sys", lambda: {"at": 0.0, "value": None})
        if time.monotonic() - kept["at"] > 0.5:  # several screens may ask at once
            kept["value"] = {**hardware.memory_now(), "disk": hardware.disk(_paths(req.app).get("memory")
                                                                            or Path.home())}
            kept["at"] = time.monotonic()
        return kept["value"]

    def lines(kind: str):
        def read(req: Request) -> dict:
            tail = _tail(req.app, kind)
            if tail is None:
                return {"next": 0, "total": 0, "events": []}
            after = req.int("after", None, lo=0)
            return tail.read(after, limit=req.int("limit", 500, lo=0, hi=500), tail=req.int("tail", 0, lo=0, hi=500))
        read.__name__ = f"read_{kind}"
        return read

    routes.add("GET", "/api/events", lines("events"), __name__)
    routes.add("GET", "/api/metrics", lines("metrics"), __name__)

    @routes.get("/api/metrics/summary")
    def metrics_summary(req: Request) -> dict:
        from camr_engine.metrics import Meter, summary

        path = _paths(req.app).get("metrics")
        return summary(Meter.read(Path(path))) if path else {"answers": 0}
