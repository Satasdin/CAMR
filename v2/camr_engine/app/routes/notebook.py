"""The Notebook and Script tabs' routes: a notebook or a .py file of the open project (the Code screen's workspace),
read, edited and run by the person in the app (camr_engine.notebooks). The person pressing Run is their approval; the
agent's own runs ask at the gate (camr_engine.agentic.tools).

- ``GET /api/notebook?path=``: its cells and outputs (images as base64 PNG, simple tables as rows) and its run;
- ``POST /api/notebook/cell`` ``{path, index, source, kind, op}``: change a cell (op edit, insert or delete);
- ``POST /api/notebook/run`` ``{path, cell}``: run one cell, or every cell from a fresh kernel (no cell); it runs
  in the background, and ``GET /api/notebook`` shows which cell is running and each cell's outputs as it ends;
- ``POST /api/notebook/stop`` ``{path}``;
- ``GET /api/script?path=``; ``POST /api/script/run`` ``{path}``; ``POST /api/script/stop`` ``{path}``: a .py file,
  its last run's output and the pictures it made;
- ``GET /api/notebook/env``; ``POST /api/notebook/env``: whether the notebook Python is set up, and setting it up
  (once, in the background).
"""

from __future__ import annotations

import threading
import time

from camr_engine import notebooks as nbm
from camr_engine.agentic.workspace import Outside
from camr_engine.app.routes.code import desk
from camr_engine.app.web import Refused, Request, Routes, part

PATH = 1024


def _ws(req: Request):
    ws = desk(req.app).workspace
    if ws is None:
        raise Refused(409, "open a project first")
    return ws


def guard(fn):
    def run(req: Request):
        try:
            return fn(req)
        except Outside as e:
            raise Refused(400, str(e)) from None
        except nbm.Failed as e:
            raise Refused(503, str(e)) from None
        except RuntimeError as e:  # running already
            raise Refused(409, str(e)) from None
        except ValueError as e:
            raise Refused(400, str(e)) from None
    run.__name__ = fn.__name__
    run.__module__ = fn.__module__
    return run


class Scripts:
    """Each script's latest run, by its full path."""

    def __init__(self):
        self.lock = threading.Lock()
        self.runs: dict[str, dict] = {}
        self.cancels: dict[str, threading.Event] = {}


def _scripts(app) -> Scripts:
    return part(app, "_notebook_scripts", Scripts)


def _env_job(app) -> dict:
    return part(app, "_notebook_env", lambda: {"state": "idle", "error": None, "versions": None})


def register(routes: Routes) -> None:
    @routes.get("/api/notebook")
    @guard
    def notebook(req: Request) -> dict:
        ws = _ws(req)
        path = req.str("path", limit=PATH)
        nb = nbm.load(ws, path)
        return {"path": ws.rel(ws.path(path)), **nbm.view(nb), "run": nbm.NOTEBOOKS.state(ws, path),
                "sandboxed": nbm.sandbox_works(), "ready": nbm.kernel_ready()}

    @routes.post("/api/notebook/cell")
    @guard
    def cell(req: Request) -> dict:
        ws = _ws(req)
        path = req.str("path", limit=PATH)
        source = req.body.get("source")
        if source is not None and not isinstance(source, str):
            raise Refused(400, "source is the cell's text")
        index = req.int("index", None)
        if index is None:
            raise Refused(400, "give the cell's index")
        kind = req.str("kind", limit=20) or None
        nb, _ = nbm.edit_cell(ws, path, index, source, kind=kind, op=req.str("op", "edit", limit=10))
        return {"path": path, **nbm.view(nb), "run": nbm.NOTEBOOKS.state(ws, path)}

    @routes.post("/api/notebook/run")
    @guard
    def run(req: Request) -> dict:
        ws = _ws(req)
        path = req.str("path", limit=PATH)
        cell = req.int("cell", None)
        return nbm.NOTEBOOKS.start(ws, path, cell)

    @routes.post("/api/notebook/stop")
    @guard
    def stop(req: Request) -> dict:
        ws = _ws(req)
        return nbm.NOTEBOOKS.stop(ws, req.str("path", limit=PATH))

    @routes.get("/api/script")
    @guard
    def script(req: Request) -> dict:
        ws = _ws(req)
        path = req.str("path", limit=PATH)
        if not path.lower().endswith(".py"):
            raise Refused(400, "a script is a .py file")
        rel, text = ws.text(path)
        s = _scripts(req.app)
        with s.lock:
            last = dict(s.runs.get(str(ws.path(path))) or {"state": "idle"})
        images = []
        for f in last.get("made") or []:
            got = nbm.image_b64(ws, f) if f.lower().endswith((".png", ".jpg", ".jpeg")) else None
            if got:
                images.append({"path": f, "base64": got})
        return {"path": rel, "source": text, "run": last, "images": images[:6], "sandboxed": nbm.sandbox_works(),
                "ready": nbm.kernel_ready()}

    @routes.post("/api/script/run")
    @guard
    def script_run(req: Request) -> dict:
        ws = _ws(req)
        path = req.str("path", limit=PATH)
        if not path.lower().endswith(".py") or not ws.path(path).is_file():
            raise Refused(400, "a script is a .py file of the project")
        key = str(ws.path(path))
        s = _scripts(req.app)
        ev = threading.Event()
        with s.lock:
            if s.runs.get(key, {}).get("state") == "running":
                raise Refused(409, f"{path} is running already")
            s.runs[key] = {"state": "running", "started": time.time()}
            s.cancels[key] = ev

        def go():
            try:
                got = nbm.run_script(ws, path, cancel=ev)
                state = "stopped" if ev.is_set() else "timeout" if got["timed_out"] else (
                    "done" if got["code"] == 0 else "error")
                out = {**got, "state": state}
            except Exception as e:  # noqa: BLE001 (shown in the tab)
                out = {"state": "failed", "error": f"{e}"[:500]}
            with s.lock:
                s.runs[key] = {**out, "started": s.runs[key].get("started"), "ended": time.time()}
                s.cancels.pop(key, None)

        threading.Thread(target=go, daemon=True, name=f"script {path}").start()
        return {"state": "running"}

    @routes.post("/api/script/stop")
    @guard
    def script_stop(req: Request) -> dict:
        ws = _ws(req)
        s = _scripts(req.app)
        with s.lock:
            ev = s.cancels.get(str(ws.path(req.str("path", limit=PATH))))
        if ev is not None:
            ev.set()
        return {"stopping": ev is not None}

    @routes.get("/api/notebook/env")
    @guard
    def env(req: Request) -> dict:
        return {"ready": nbm.kernel_ready(), "path": str(nbm.kernel_env()), "sandboxed": nbm.sandbox_works(),
                "job": dict(_env_job(req.app))}

    @routes.post("/api/notebook/env")
    @guard
    def env_make(req: Request) -> dict:
        job = _env_job(req.app)
        if job["state"] != "running":
            job.update(state="running", error=None)

            def go():
                try:
                    job.update(state="done", versions=nbm.ensure_kernel_env(log=lambda _line: None)["versions"])
                except Exception as e:  # noqa: BLE001 (shown in the app)
                    job.update(state="failed", error=f"{e}"[:1000])

            threading.Thread(target=go, daemon=True, name="notebook env").start()
        return env(req)
