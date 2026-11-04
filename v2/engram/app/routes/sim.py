"""The scripted lives: load one into the memory and quiz it (``/api/life``, ``/api/quiz``), or watch one arrive day by
day in its own memory (``/api/sim/*``)."""

from __future__ import annotations

from engram.app.web import Refused, Request, Routes


def _app(req: Request):
    if not hasattr(req.app, "simulate"):
        raise Refused(409, "this app has no models loaded (a fixture is read-only)")
    return req.app


def register(routes: Routes) -> None:
    @routes.get("/api/sim/state")
    def sim_state(req: Request) -> dict:
        sim = getattr(req.app, "sim", None)
        return sim.state() if sim else {"day": -1, "idle": True}

    @routes.get("/api/sim/brain")
    def sim_brain(req: Request) -> dict:
        sim = getattr(req.app, "sim", None)
        if not sim or sim.layout is None:
            return {"moments": [], "rooms": [], "layout": [], "answers": []}
        return {**req.app.brain(sim.memory, sim.layout), "full": sim.layout}

    @routes.post("/api/life")
    def life(req: Request) -> dict:
        return _app(req).load_life(req.str("persona", "farmer", limit=40), req.int("seed", 0))

    @routes.post("/api/sim/start")
    def sim_start(req: Request) -> dict:
        return _app(req).simulate(req.str("persona", "farmer", limit=40), req.int("seed", 1),
                                  req.int("questions", 25))

    @routes.post("/api/sim/stop")
    def sim_stop(req: Request) -> dict:
        sim = getattr(req.app, "sim", None)
        if sim:
            sim.stop()
        return {"stopped": True}

    @routes.post("/api/quiz")
    def quiz(req: Request) -> dict:
        return _app(req).quiz(req.str("persona", "farmer", limit=40), req.int("seed", 0), req.bool("errands"),
                              req.int("limit", 100))
