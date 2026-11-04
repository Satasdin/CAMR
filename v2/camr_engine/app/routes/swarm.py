"""The Swarm screen's routes: N agents on one task, each with its own agent reach, sharing one RAM budget.

- ``POST /api/swarm/start`` ``{task, n, persona, memory}``: one line is one task for every agent; several lines are a
  queue the agents share;
- ``POST /api/swarm/stop``;
- ``GET /api/swarm/state``: each agent's tokens, tasks done, time, spans and memory ticks, its well (its own
  reach's rooms), the board of finished tasks, the shared RAM over time, and what waits for approval.

Approvals go through ``POST /api/code/approve``, the same gate as the Code screen.
"""

from __future__ import annotations

from camr_engine.app.routes.code import desk, guard, model_label
from camr_engine.app.web import Refused, Request, Routes


def register(routes: Routes) -> None:
    @routes.post("/api/swarm/start")
    @guard
    def start(req: Request) -> dict:
        memory = req.body.get("memory")
        s = desk(req.app).start_swarm(req.str("task", limit=8000), req.int("n", 4, lo=1, hi=8),
                                      persona=req.str("persona", limit=40) or None,
                                      memory=memory if isinstance(memory, bool) else True)
        return s.snapshot()

    @routes.post("/api/swarm/stop")
    @guard
    def stop(req: Request) -> dict:
        s = desk(req.app).swarm
        if s is None:
            raise Refused(404, "no swarm has run")
        s.stop()
        return {"stopped": s.id}

    @routes.get("/api/swarm/state")
    @guard
    def state(req: Request) -> dict:
        d = desk(req.app)
        return {"swarm": d.swarm.snapshot() if d.swarm is not None else None, "can_run": d.can_swarm(),
                "model": model_label(req.app), "persona": d.settings["persona"], "memory": d.settings["memory"],
                "personas": [{"id": p.id, "name": p.name} for p in d.personas.all()],
                "workspace": d.workspace.name if d.workspace else None}
