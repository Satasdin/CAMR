"""The Code screen's routes: a workspace, its files, threads of tasks for the local model, and the approvals that let
each shell command and MCP call run.

- ``GET /api/code/state``: the workspace, threads, personas, skills, MCP servers, what is waiting for approval, and
  whether a run can start;
- ``POST /api/code/workspace`` ``{path}``: choose the folder (checked: not the disk, the home folder or a folder of
  keys);
- ``GET /api/code/files``; ``GET /api/code/file?path=``; ``POST /api/code/file`` ``{path, text, base}``: the
  editor, confined to the workspace, with the memory gutter's marks (a saved fix answers with ``fix`` and ``kept``,
  the reach it is kept in);
- ``POST /api/code/thread`` ``{title, persona}``; ``GET /api/code/thread?id=``;
- ``POST /api/code/run`` ``{thread, task, memory, persona}`` (the persona runs, whatever the thread ran as
  before); ``GET /api/code/run?id=&term=N``;
  ``GET /api/code/live?id=&from=N``: the run's live events (camr_engine.live: each word with its layers' activity,
  and the room each step read); ``POST /api/code/stop`` ``{run}``;
- ``POST /api/code/approve`` ``{id, allow}``: ``allow`` must be ``true`` exactly to run the action;
- ``GET /api/code/moment?reach=&id=``: a moment's words, for the gutter;
- ``POST /api/code/settings`` ``{memory, persona, skills}``; ``POST /api/code/persona``,
  ``/api/code/persona/delete``; ``GET /api/code/skill?name=``;
- ``POST /api/code/mcp/add`` ``{name, command, env}``, ``/remove``, ``/connect``, ``/disconnect`` ``{name}``.

The page is the only client (the server checks its launch token on every call); the model can reach none of these.
"""

from __future__ import annotations

import os

from pathlib import Path

from camr_engine.agentic.desk import Busy, Desk, engine_brains
from camr_engine.agentic.servers import spec
from camr_engine.agentic.workspace import Outside
from camr_engine.app.web import Refused, Request, Routes, part


class OnSessionThread:
    """A brain whose model calls run on the chat session's own thread. MLX's streams belong to the thread that made
    them, so the chat and the agent must share one to use the one model in turn."""

    def __init__(self, brain, run):
        self.brain, self.run = brain, run

    def __getattr__(self, name):
        return getattr(self.brain, name)

    def think(self, prompt):
        return self.run(lambda: self.brain.think(prompt))

    def keep(self, text, to=None, source="model"):
        return self.run(lambda: self.brain.keep(text, to, source))

    def close(self):
        return self.run(self.brain.close)


def on_session_thread(app, make):
    """Brains made and used on the chat session's thread, when the app has a chat."""
    if make is None:
        return None

    def made(spec):
        from camr_engine.app.routes.chat import talk

        t = talk(app)
        if t is None:
            return make(spec)
        return OnSessionThread(t.run(lambda: make(spec)), t.run)

    return made


def agent_brains(local, chosen):
    """The agent's model: the app's own (with CAMR memory) unless another is chosen, by CAMR_AGENT_MODEL or the
    desk's setting: "claude-..." (the side-by-side, metered and capped) or "ollama:<name>" (a model in Ollama, its
    facts as text, as Ollama lets nothing reach the model's KV cache). None when the app has no model of its own (a
    read-only fixture): then nothing runs."""
    if local is None:
        return None

    def make(spec):
        other = os.environ.get("CAMR_AGENT_MODEL") or chosen() or ""
        if other.startswith("claude-"):
            from camr_engine.agentic.claude_brain import ClaudeBrain

            return ClaudeBrain(other)
        if other.startswith("ollama:"):
            from camr_engine.agentic.ollama_brain import OllamaBrain

            return OllamaBrain(other.removeprefix("ollama:"))
        return local(spec)

    return make


def desk(app) -> Desk:
    """The app's one Desk, made on first use. A workspace may neither hold nor sit inside its folder, the app's memory
    or the memory's reaches."""
    def make() -> Desk:
        from camr_engine.app.measuring import active
        from camr_engine.reach import KINDS

        memory = getattr(app, "memory", None)
        base = Path(memory.path).parent if memory is not None else Path.home() / ".camr"
        root = getattr(app, "agentic_root", None) or base / "code"
        keep_out = [Path(memory.path), *(base / k for k in KINDS)] if memory is not None else []
        brains = getattr(app, "brain_factory", None) or on_session_thread(app, engine_brains(app))
        brains = agent_brains(brains, lambda: d.settings.get("agent_model"))
        d = Desk(Path(root), brains=brains, model_lock=getattr(app, "lock", None), measuring=active,
                 skills_dir=getattr(app, "skills_dir", None), keep_out=keep_out)
        from camr_engine.app.routes.chat import talk
        from camr_engine.shelves import SHELVES

        # the agent in the one window reads the chat's shelves and is checked against its memory; the chat is looked
        # up when it is used, as asking for it here, while this part is being made, would wait on itself
        def shelf_notes(name: str, question: str):
            t = talk(app)
            return t.shelf_notes(name, question) if t is not None else None

        def fact_check(text: str) -> list[str]:
            t = talk(app)
            return t.page_check(text) if t is not None else []

        def told(request: str) -> list[str]:
            t = talk(app)
            return t.told_about(request) if t is not None else []

        d.shelf_notes, d.fact_check, d.told = shelf_notes, fact_check, told
        d.shelf_index = lambda: "\n".join(f"- {s.name}: {s.about[:120]}" for s in SHELVES)
        return d

    return part(app, "_code_desk", make)


def guard(fn):
    """Turn the agent package's refusals into the server's."""
    def run(req: Request):
        try:
            return fn(req)
        except Outside as e:
            raise Refused(400, str(e)) from None
        except Busy as e:
            raise Refused(409, str(e)) from None
        except KeyError as e:
            raise Refused(404, f"not found: {e.args[0] if e.args else ''}") from None
        except ValueError as e:
            raise Refused(400, str(e)) from None
    run.__name__ = fn.__name__
    run.__module__ = fn.__module__
    return run


def model_label(app) -> str | None:
    runtime = getattr(app, "models", None)
    if runtime is not None:
        s = runtime.state()
        slot = s.get("memory") or s.get("picked")
        if slot and slot.get("repo"):
            return slot["repo"]
    return getattr(getattr(app, "reader", None), "repo", None)


def register(routes: Routes) -> None:
    @routes.get("/api/code/state")
    @guard
    def state(req: Request) -> dict:
        return {**desk(req.app).state(), "model": model_label(req.app)}

    @routes.post("/api/code/workspace")
    @guard
    def workspace(req: Request) -> dict:
        return desk(req.app).set_workspace(req.str("path", limit=1024))

    @routes.get("/api/code/files")
    @guard
    def files(req: Request) -> dict:
        d = desk(req.app)
        if d.workspace is None:
            return {"root": None, "files": []}
        return {"root": str(d.workspace.root), "files": d.workspace.tree()}

    @routes.get("/api/code/file")
    @guard
    def file_get(req: Request) -> dict:
        return desk(req.app).open_file(req.str("path", limit=1024))

    @routes.post("/api/code/file")
    @guard
    def file_save(req: Request) -> dict:
        text = req.body.get("text")
        if not isinstance(text, str):
            raise Refused(400, "send the file's text")
        base = req.body.get("base")
        return desk(req.app).save_file(req.str("path", limit=1024), text, base if isinstance(base, str) else None)

    @routes.post("/api/code/thread")
    @guard
    def thread_new(req: Request) -> dict:
        persona = req.str("persona", limit=40) or None
        return desk(req.app).new_thread(req.str("title", limit=200), persona)

    @routes.get("/api/code/thread")
    @guard
    def thread_get(req: Request) -> dict:
        d = desk(req.app)
        t = d.thread(req.str("id", limit=40))
        live = [r.snapshot() for r in d.live_runs() if r.thread_id == t["id"]]
        return {**t, "live": live[0] if live else None}

    @routes.post("/api/code/run")
    @guard
    def run_start(req: Request) -> dict:
        memory = req.body.get("memory")
        context = req.body.get("context")
        context = [str(c)[:1000] for c in context[:8]] if isinstance(context, list) else None
        run = desk(req.app).start(req.str("thread", limit=40), req.str("task", limit=8000),
                                  memory=memory if isinstance(memory, bool) else None,
                                  persona=req.str("persona", limit=40) or None, window=req.bool("window"),
                                  max_steps=req.int("max_steps", None, lo=1, hi=60), context=context)
        return run.snapshot()

    @routes.post("/api/code/build")
    @guard
    def build_start(req: Request) -> dict:
        """Plan a request, then build it part by part (camr_engine.agentic.plan)."""
        memory = req.body.get("memory")
        lead = desk(req.app).build(req.str("thread", limit=40), req.str("request", limit=4000),
                                   memory=memory if isinstance(memory, bool) else None)
        return lead.snapshot()

    @routes.get("/api/code/build")
    @guard
    def build_get(req: Request) -> dict:
        return desk(req.app).lead(req.str("id", limit=80)).snapshot()

    @routes.post("/api/code/build/stop")
    @guard
    def build_stop(req: Request) -> dict:
        lead = desk(req.app).lead(req.str("id", limit=80))
        lead.stop()
        return lead.snapshot()

    @routes.post("/api/code/answer")
    @guard
    def answer(req: Request) -> dict:
        reply = req.body.get("text")
        if not isinstance(reply, str) or len(reply) > 200_000:
            raise Refused(400, "text is the answer")
        return desk(req.app).gate.answer(req.str("id", limit=40), reply).show()

    @routes.get("/api/code/run")
    @guard
    def run_get(req: Request) -> dict:
        return desk(req.app).run(req.str("id", limit=80)).snapshot(req.int("term", 0, lo=0), req.int("turns", 0, lo=0))

    @routes.get("/api/code/live")
    @guard
    def run_live(req: Request) -> dict:
        return desk(req.app).run(req.str("id", limit=80)).watch.since(req.int("from", 0, lo=0) or 0)

    @routes.post("/api/code/stop")
    @guard
    def run_stop(req: Request) -> dict:
        return desk(req.app).stop(req.str("run", limit=80))

    @routes.post("/api/code/approve")
    @guard
    def approve(req: Request) -> dict:
        allow = req.body.get("allow")
        if not isinstance(allow, bool):
            raise Refused(400, "allow is true or false")
        return desk(req.app).gate.decide(req.str("id", limit=40), allow).show()

    @routes.get("/api/code/moment")
    @guard
    def moment(req: Request) -> dict:
        got = desk(req.app).moment(req.str("reach", limit=100), req.int("id", 0, lo=0))
        if got is None:
            raise Refused(404, "that moment is not in an open memory")
        return got

    @routes.post("/api/code/settings")
    @guard
    def settings(req: Request) -> dict:
        memory = req.body.get("memory")
        skills = req.body.get("skills")
        return desk(req.app).configure(memory=memory if isinstance(memory, bool) else None,
                                       persona=req.str("persona", limit=40) or None,
                                       skills=skills if isinstance(skills, str) else None,
                                       window_tokens=req.int("window_tokens", None, lo=0, hi=262_144),
                                       agent_model=req.body.get("agent_model") if isinstance(
                                           req.body.get("agent_model"), str) else None)

    @routes.get("/api/code/models")
    @guard
    def other_models(req: Request) -> dict:
        """Models the agent can use besides the app's own: Ollama's, here."""
        from camr_engine.agentic.ollama_brain import models

        return {"ollama": models(), "chosen": desk(req.app).state().get("agent_model")}

    @routes.post("/api/code/persona")
    @guard
    def persona_save(req: Request) -> dict:
        d = desk(req.app)
        return {"saved": d.personas.save(req.body).show(), "personas": [p.show() for p in d.personas.all()]}

    @routes.post("/api/code/persona/delete")
    @guard
    def persona_delete(req: Request) -> dict:
        d = desk(req.app)
        d.personas.delete(req.str("id", limit=40))
        return {"personas": [p.show() for p in d.personas.all()]}

    @routes.get("/api/code/skill")
    @guard
    def skill(req: Request) -> dict:
        name = req.str("name", limit=64)
        return {"name": name, "text": desk(req.app).skills.load(name)}

    @routes.post("/api/code/mcp/add")
    @guard
    def mcp_add(req: Request) -> dict:
        env = req.body.get("env") or {}
        if not isinstance(env, dict) or not all(isinstance(v, str) for v in env.values()):
            raise Refused(400, "env is an object of text values")
        s = spec(req.str("name", limit=40), req.str("command", limit=2000), env)
        return {"servers": desk(req.app).servers.add(s)}

    @routes.post("/api/code/mcp/remove")
    @guard
    def mcp_remove(req: Request) -> dict:
        return {"servers": desk(req.app).servers.remove(req.str("name", limit=40))}

    @routes.post("/api/code/mcp/connect")
    @guard
    def mcp_connect(req: Request) -> dict:
        d = desk(req.app)
        d.servers.connect(req.str("name", limit=40), d.workspace.root if d.workspace else None)
        return {"servers": d.servers.show()}

    @routes.post("/api/code/mcp/disconnect")
    @guard
    def mcp_disconnect(req: Request) -> dict:
        d = desk(req.app)
        d.servers.disconnect(req.str("name", limit=40))
        return {"servers": d.servers.show()}
