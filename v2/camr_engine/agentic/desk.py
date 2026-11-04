"""What the Code screen keeps between requests: the workspace, its threads and runs, the personas, the skills, the MCP
servers, the gate and the memory gutter. Everything lives under one folder (``~/.camr/code`` beside the memory):

    settings.json        the workspace, recent workspaces, memory on or off, the persona, the skills folder
    threads/<id>.json    each thread with its finished runs
    personas.json        personas a person saved
    mcp.json             MCP servers a person added (this user only)
    marks/<ws>.json      the memory gutter, per workspace
    logs/<server>.log    each MCP server's errors

A thread is one conversation, with a session reach of its own (``session:<thread id>``); the project reach is named
after the workspace folder, and the agent reach after the persona. The persona chosen in the rack is the one that
runs, in any thread. The model is made by ``brains``, given what to open:
``{"memory", "session", "project", "agent", "reads", "writes", "pool"}``, so tests pass fakes and the app passes the
engine (``engine_brains``). Every Code thread shares one RAM budget for hot rooms (one ``swap.Pool``, the Desk's).

A person's fix to the agent's code (saved in the editor) is told to the next run in that workspace, and, with memory
on, kept in the project's memory as a "Your fix" moment, so later answers can lean on it and the gutter can show it.
The workspace may neither hold nor sit inside this folder or the memory's (``keep_out``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable

from camr_engine.agentic.brain import FIX, Brain
from camr_engine.agentic.gate import Gate
from camr_engine.agentic.loop import Run
from camr_engine.agentic.marks import Marks
from camr_engine.agentic.personas import Persona, Personas
from camr_engine.agentic.servers import Servers
from camr_engine.agentic.skills import Skills
from camr_engine.agentic.tools import Toolbox
from camr_engine.agentic.workspace import Outside, Workspace, check_root, sha

MAX_RUNS = 40  # runs kept in RAM (finished ones are in their thread's file too)
MAX_THREADS = 200
RECENT = 8
FIXES = 8  # fixes told to the next run, per workspace
TERM_FILED = 8_000  # characters of a run's terminal kept in its thread's file (the run's turns hold what it read)
_THREAD = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")


CODING_SHELF = "project:coding"  # where Code keeps what it learns; its workspace's own reach is read too

class Busy(RuntimeError):
    """Something already running stands in the way."""


def slug(name: str) -> str:
    """A reach name from a folder name: letters, digits, ``.``, ``_`` and ``-``."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")[:64]
    return s if s and s[0].isalnum() else f"w{s}"[:64] if s else "workspace"


def thread_id() -> str:
    import secrets

    return f"{dt.datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


class Desk:
    def __init__(self, root: Path, *, brains: Callable[[dict], Brain] | None = None,
                 model_lock: threading.Lock | None = None, skills_dir: Path | None = None,
                 measuring: Callable[[], dict | None] | None = None, keep_out: list[Path] | None = None):
        self.root = Path(root)  # made on the first write, so looking never leaves a folder behind
        self.brains = brains
        self.model_lock = model_lock or threading.Lock()
        self.measuring = measuring
        self.keep_out = [self.root, *(Path(p) for p in keep_out or [])]  # never inside a workspace, nor holding one
        self.lock = threading.RLock()
        self.gate = Gate()
        self.personas = Personas(self.root / "personas.json")
        self.servers = Servers(self.root / "mcp.json", self.root / "logs")
        self.default_skills = Path(skills_dir) if skills_dir else self.root.parent / "skills"
        self.settings = self._load_settings()
        self.workspace: Workspace | None = None
        if self.settings.get("workspace"):
            try:
                self.workspace = Workspace(self.settings["workspace"], self.keep_out)
            except Outside:
                self.workspace = None
        self.runs: dict[str, Run] = {}
        self.open: dict[tuple, Brain] = {}  # brains kept open between runs, by what they read
        self.used_tools: set[str] = set()
        self.pool = None  # one RAM budget for the hot rooms of every thread's memory
        self._marks: dict[str, Marks] = {}  # one per workspace, shared by runs and the editor
        self._keeping: list[threading.Thread] = []  # fixes being kept in memory
        self._listed: dict[Path, tuple[float, dict]] = {}  # thread file -> (its mtime, its line in the list)

    # -- settings

    def _load_settings(self) -> dict:
        try:
            got = json.loads((self.root / "settings.json").read_text())
        except (OSError, ValueError):
            got = {}
        fixes = got.get("fixes") if isinstance(got.get("fixes"), dict) else {}
        return {"workspace": got.get("workspace"), "recent": list(got.get("recent") or [])[:RECENT],
                "memory": bool(got.get("memory", True)), "persona": str(got.get("persona") or "coder"),
                "skills": got.get("skills"),
                "fixes": {str(k): [str(x) for x in v][-FIXES:] for k, v in fixes.items() if isinstance(v, list)}}

    def _save_settings(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / "settings.tmp"
        tmp.write_text(json.dumps(self.settings, indent=1))
        os.replace(tmp, self.root / "settings.json")

    def configure(self, *, memory: bool | None = None, persona: str | None = None,
                  skills: str | None = None) -> dict:
        with self.lock:
            if memory is not None:
                self.settings["memory"] = bool(memory)
            if persona is not None:
                self.personas.get(persona)  # KeyError for an unknown one
                self.settings["persona"] = persona
            if skills is not None:
                p = Path(skills).expanduser()
                if skills and not p.is_absolute():
                    raise ValueError("give the skills folder by its full path")
                self.settings["skills"] = str(p) if skills else None
            self._save_settings()
        return self.state()

    @property
    def skills(self) -> Skills:
        return Skills(Path(self.settings["skills"]) if self.settings.get("skills") else self.default_skills)

    def set_workspace(self, path: str) -> dict:
        root = check_root(path, self.keep_out)
        with self.lock:
            if any(r.live for r in self.runs.values()):
                raise Busy("a run is going; stop it before changing the workspace")
            self.workspace = Workspace(root, self.keep_out)
            recent = [str(root)] + [r for r in self.settings["recent"] if r != str(root)]
            self.settings.update(workspace=str(root), recent=recent[:RECENT])
            self._save_settings()
            self._close_brains()
        return self.state()

    @property
    def marks(self) -> Marks | None:
        """The workspace's memory gutter: one Marks for it in this app, so runs and the editor never write over
        each other's marks."""
        if self.workspace is None:
            return None
        key = hashlib.sha1(str(self.workspace.root).encode()).hexdigest()[:12]
        with self.lock:
            got = self._marks.get(key)
            if got is None:
                got = self._marks[key] = Marks(self.root / "marks" / f"{key}.json")
            return got

    @property
    def fixes(self) -> list[str]:
        """The fixes saved in this workspace since its last run, told to the next one."""
        if self.workspace is None:
            return []
        return list(self.settings["fixes"].get(str(self.workspace.root), []))

    def _take_fixes(self) -> list[str]:
        with self.lock:
            got = self.settings["fixes"].pop(str(self.workspace.root), [])
            if got:
                self._save_settings()
            return got

    def _pool(self):
        """The one RAM budget for hot rooms, made on first use."""
        with self.lock:
            if self.pool is None:
                from camr_engine.swap import Pool

                self.pool = Pool()
            return self.pool

    # -- threads

    def _thread_path(self, tid: str) -> Path:
        if not _THREAD.match(tid or ""):
            raise KeyError(tid)
        return self.root / "threads" / f"{tid}.json"

    def thread(self, tid: str) -> dict:
        try:
            return json.loads(self._thread_path(tid).read_text())
        except (OSError, ValueError):
            raise KeyError(tid) from None

    def _write_thread(self, t: dict) -> None:
        p = self._thread_path(t["id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(t))
        os.replace(tmp, p)

    def new_thread(self, title: str = "", persona: str | None = None) -> dict:
        persona = persona or self.settings["persona"]
        self.personas.get(persona)
        t = {"id": thread_id(), "title": " ".join(title.split())[:80], "persona": persona, "created": time.time(),
             "workspace": str(self.workspace.root) if self.workspace else None, "runs": []}
        self._write_thread(t)
        return t

    def threads(self) -> list[dict]:
        """Every thread, newest first, each with its last answer's path strip (read again only when its file
        changed)."""
        folder = self.root / "threads"
        out = []
        live_runs = self.live_runs()
        for p in sorted(folder.glob("*.json"), reverse=True)[:MAX_THREADS] if folder.is_dir() else []:
            try:
                mtime = p.stat().st_mtime
                got = self._listed.get(p)
                if got is None or got[0] != mtime:
                    t = json.loads(p.read_text())
                    last = t["runs"][-1] if t.get("runs") else None
                    got = (mtime, {"id": t["id"], "title": t.get("title") or (last["task"][:60] if last
                                                                             else "new thread"),
                                   "persona": t.get("persona"), "created": t.get("created"),
                                   "runs": len(t.get("runs", [])), "workspace": t.get("workspace"),
                                   "last": _strip(last) if last else None})
                    self._listed[p] = got
            except (OSError, ValueError, KeyError):
                continue
            live = next((r for r in live_runs if r.thread_id == got[1]["id"]), None)
            out.append({**got[1], "live": live.id if live else None})
        return out

    # -- runs

    def can_run(self) -> str | None:
        """Why a run cannot start now, or None."""
        if self.brains is None:
            return "no model here (a fixture is read-only)"
        if self.measuring is not None and self.measuring():
            return f"a benchmark is measuring ({self.measuring()['job']}); try again when it is done"
        if self.workspace is None:
            return "choose a workspace first"
        return None

    def brain_for(self, persona: Persona, thread: str | None, memory: bool) -> Brain:
        """The model for a thread's run: kept open between runs while it reads the same reaches."""
        project = slug(self.workspace.name) if self.workspace else None
        reads = [r for r in persona.reads if (r != "session" or thread) and (r != "project" or project)]
        writes = persona.writes if persona.writes in reads else (reads[0] if reads else "agent")
        if not reads:
            reads, writes = ["agent"], "agent"
        if "project" in reads:  # the Coding shelf (camr_engine.shelves) holds code work from every workspace
            reads = [*reads, CODING_SHELF]
            writes = CODING_SHELF if writes == "project" else writes
        spec = {"memory": memory, "session": thread, "project": project, "agent": persona.id, "reads": reads,
                "writes": writes, "pool": self._pool() if memory else None}
        key = (memory, thread, project, persona.id, tuple(reads), writes)
        with self.lock:
            got = self.open.get(key)
            if got is not None:
                return got
            busy = {id(r.brain) for r in self.runs.values() if r.live}
            idle = [k for k, b in self.open.items() if id(b) not in busy]
            while len(self.open) >= 3 and idle:  # a few reach sessions stay open; the oldest idle one closes
                self.open.pop(idle.pop(0)).close()
            b = self.brains(spec)
            self.open[key] = b
            return b

    def start(self, thread: str, task: str, *, memory: bool | None = None, persona: str | None = None,
              max_steps: int | None = None) -> Run:
        """Start a task in a thread, as ``persona`` (by default the one chosen in the rack, whatever the thread ran
        as before: the thread takes it on)."""
        why = self.can_run()
        if why:
            raise Busy(why)
        task = task.strip()
        if not task:
            raise ValueError("give the agent a task")
        t = self.thread(thread)
        p = self.personas.get(persona or self.settings["persona"])
        memory = self.settings["memory"] if memory is None else bool(memory)
        with self.lock:
            if any(r.live and r.thread_id == thread for r in self.runs.values()):
                raise Busy("this thread is running already")
            brain = self.brain_for(p, thread, memory)
            notes = self._take_fixes()
            tools = Toolbox(self.workspace, self.gate, skills=self.skills, servers=self.servers, allows=p.allows)
            t["count"] = int(t.get("count", len(t.get("runs", [])))) + 1  # runs ever started (the file keeps 20)
            rid = f"{thread}-{t['count']}"
            run = Run(rid, task, brain=brain, tools=tools, persona=p, gate=self.gate, model_lock=self.model_lock,
                      label=t.get("title") or task[:40], workspace=self.workspace.name, skills=self.skills.index(),
                      marks=self.marks, notes=notes, max_steps=max_steps or 12, measuring=self.measuring,
                      on_step=self._watch)
            run.thread_id = thread
            self.runs[rid] = run
            finished = [k for k, r in self.runs.items() if not r.live]
            for k in finished[:max(0, len(self.runs) - MAX_RUNS)]:
                del self.runs[k]
            t["persona"] = p.id
            t["title"] = t.get("title") or task[:80]
            self._write_thread(t)
        run.start()
        return run

    def _watch(self, run: Run, turn: dict) -> None:
        if turn["kind"] == "call":
            self.used_tools.add(turn["tool"])
        if turn["kind"] in ("answer", "stopped", "error", "kept"):
            self._file(run)

    def _file(self, run: Run) -> None:
        """Keep the run in its thread's file (again, as it changes at its end)."""
        with self.lock:
            try:
                t = self.thread(run.thread_id)
            except KeyError:
                return
            snap = run.snapshot()
            snap.pop("turns_from", None)
            snap["state"] = run.state if not run.live else ("done" if run.answer else run.state)
            snap.pop("waiting", None)
            term = "".join(snap["term"])  # only its end: a chatty command never swells the file
            if len(term) > TERM_FILED or snap.get("term_cut"):
                term = "… earlier output left out …\r\n" + term[-TERM_FILED:]
            snap["term"] = [term] if term else []
            runs = [r for r in t.get("runs", []) if r["id"] != run.id]
            t["runs"] = (runs + [snap])[-20:]
            self._write_thread(t)

    def live_runs(self) -> list[Run]:
        with self.lock:
            return [r for r in self.runs.values() if r.live]

    def run(self, rid: str) -> Run:
        got = self.runs.get(rid)
        if got is None:
            raise KeyError(rid)
        return got

    def stop(self, rid: str) -> dict:
        r = self.run(rid)
        r.stop()
        return {"stopped": rid}

    # -- the editor

    def save_file(self, rel: str, text: str, base: str | None) -> dict:
        """A person saved a file in the editor. ``base`` is the text's hash when it was opened: if the file changed
        since (the agent wrote it), nothing is written and the page is told. A fix to the agent's code is marked,
        told to the workspace's next run, and (memory on) kept in the project's memory; ``kept`` names that reach."""
        ws = self._ws()
        path = ws.path(rel, write=True)
        before = ws.text(ws.rel(path))[1] if path.exists() else ""
        if base is not None and path.exists() and sha(before) != base:
            raise Busy("the file changed since you opened it (the agent may have written it); reopen it first")
        w = ws.write(rel, text)
        marks = self.marks
        got, pairs = marks.saved(w.path, before, text) if marks is not None else ({"lines": {}}, [])
        note = kept = None
        if pairs:
            old, new = pairs[0]
            more = f" (and {len(pairs) - 1} more changes)" if len(pairs) > 1 else ""
            note = (f"{FIX} in {w.path} (kept): you changed {_quote(old) or 'nothing'} to {_quote(new) or 'nothing'}"
                    f"{more}.")
            with self.lock:
                key = str(ws.root)
                self.settings["fixes"][key] = (self.settings["fixes"].get(key, []) + [note])[-FIXES:]
                self._save_settings()
            kept = self._keep_fix(note)
        return {"path": w.path, "sha": sha(text), "marks": {str(n): m for n, m in got["lines"].items()},
                "fix": note, "kept": kept}

    def _keep_fix(self, note: str) -> str | None:
        """Keep a fix in the project's memory, in the background: once no benchmark measures, under the model lock
        (remembering reads the moment with the model). Returns the reach it goes to, or None with memory off."""
        if self.brains is None or not self.settings["memory"] or self.workspace is None:
            return None
        project = slug(self.workspace.name)
        spec = {"memory": True, "session": None, "project": project, "agent": None, "reads": ["project"],
                "writes": "project", "pool": self._pool()}

        def keep() -> None:
            while self.measuring is not None and self.measuring():
                time.sleep(1.0)
            with self.model_lock:
                try:
                    b = self.brains(spec)
                except Exception:  # noqa: BLE001 (the fix is still told to the next run)
                    return
                try:
                    b.keep(note, to="project")
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    b.close()

        th = threading.Thread(target=keep, name="keep-fix", daemon=True)
        with self.lock:
            self._keeping = [x for x in self._keeping if x.is_alive()] + [th]
        th.start()
        return f"project:{project}"

    def open_file(self, rel: str) -> dict:
        ws = self._ws()
        path, text = ws.text(rel)
        marks = self.marks.get(path, text) if self.marks is not None else {}
        return {"path": path, "text": text, "sha": sha(text), "marks": {str(n): m for n, m in marks.items()}}

    def _ws(self) -> Workspace:
        if self.workspace is None:
            raise Outside("choose a workspace first")
        return self.workspace

    def moment(self, reach: str, mid: int) -> dict | None:
        """A moment's words, for hovering the memory gutter."""
        with self.lock:
            brains = list(self.open.values())
        for b in brains:
            got = b.moment(reach, mid)
            if got is not None:
                return got
        return None

    # -- the page's view

    def state(self) -> dict:
        ws = self.workspace
        live = self.live_runs()
        return {"workspace": {"path": str(ws.root), "name": ws.name, "project": slug(ws.name)} if ws else None,
                "recent": self.settings["recent"], "memory": self.settings["memory"],
                "persona": self.settings["persona"], "personas": [p.show() for p in self.personas.all()],
                "skills": [s.show() for s in self.skills.all()], "skills_dir": str(self.skills.folder),
                "servers": self.servers.show(), "threads": self.threads(), "live": [r.id for r in live],
                "waiting": self.gate.waiting(), "can_run": self.can_run(), "used_tools": sorted(self.used_tools),
                "fixes": list(self.fixes)}

    def _close_brains(self) -> None:
        for b in self.open.values():
            try:
                b.close()
            except Exception:  # noqa: BLE001
                pass
        self.open.clear()

    def close(self) -> None:
        """Stop every run, finish keeping fixes, and close every memory and MCP server (at the app's exit).
        Commands still running are stopped too (camr_engine.agentic.shell stops them at exit in any case)."""
        for r in self.live_runs():
            r.stop()
        with self.lock:
            keeping = list(self._keeping)
        for th in keeping:
            th.join(timeout=10)
        self._close_brains()
        self.servers.close()


def _quote(text: str, limit: int = 160) -> str:
    one = " ".join(text.split())
    return f"`{one if len(one) <= limit else one[:limit] + '…'}`" if one else ""


def _strip(run: dict) -> dict:
    """A run's summary for the thread list (its last answer's path strip)."""
    model = [t for t in run.get("turns", []) if t.get("kind") == "model"]
    last = model[-1] if model else {}
    m = last.get("memory") or {}
    return {"id": run.get("id"), "task": run.get("task", "")[:120], "state": run.get("state"),
            "first_s": last.get("first_s"), "total_s": last.get("total_s"), "tier": m.get("tier"),
            "used": len(m.get("used") or []), "picked": len(m.get("nodes") or []), "read_bytes": m.get("read_bytes"),
            "seconds": m.get("seconds"), "memory": run.get("memory")}


def engine_brains(app, root: Path | None = None) -> Callable[[dict], Brain] | None:
    """The engine for the app's Code screen: a reach session over ``root`` (beside the app's memory) with
    the memory's own reader, or the plain model with memory off. None when the app has no model (a fixture)."""
    reader, embedder = getattr(app, "reader", None), getattr(app, "embedder", None)
    if reader is None or embedder is None:
        return None
    memory = getattr(app, "memory", None)
    root = Path(root) if root else (Path(memory.path).parent if memory is not None else Path.home() / ".camr")

    def make(spec: dict) -> Brain:
        from camr_engine.agentic.brain import CLOSEST, EngineBrain, PlainBrain

        if not spec["memory"]:
            runtime = getattr(app, "models", None)
            r = runtime.reader() if runtime is not None and runtime.reader() is not None else reader
            return PlainBrain(r)
        from camr_engine.reach import Session

        try:
            from camr_engine.app.server import START
        except ImportError:  # pragma: no cover
            START = dt.date(2026, 1, 5)
        s = Session(reader, embedder, root=root, name=spec.get("session"), project=spec.get("project"),
                    agent=spec.get("agent"), reads=spec["reads"], writes=spec["writes"], tiers={}, metrics=True,
                    closest=CLOSEST)
        if spec.get("pool") is not None:  # one RAM budget for every thread
            adopt(s, spec["pool"])
        return EngineBrain(s, day=lambda d: (d - START).days)

    return make


def adopt(session, pool) -> None:
    """Put the reaches a session has just opened on a shared pool. A reach another session here opened first is
    shared as it is, on the pool it was opened with, and never moved: a room is only ever counted, evicted and kept
    current in one pool."""
    own = session.pool
    for m in session.memories.values():
        t = m.tiers
        if t is None or own is None or t.pool is not own or own is pool:
            continue
        for key in [k for k in own.hot if k[0] is t]:  # none yet, as a rule: nothing was read
            pool.put(key, own.hot[key], own.sizes[key])
            own.drop(key)
        t.pool = pool
    session.pool = pool
