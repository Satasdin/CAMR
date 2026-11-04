"""A swarm: N agents (at most eight) on one task. Each agent has its own memory, the agent reach
``agent:swarm-a<n>``, which it reads and writes; all of them share one RAM budget for hot rooms (one ``swap.Pool``),
so the page can show which agent's rooms sit in RAM and when one waits for another.

The pool is the Desk's, which the Code threads share, so their rooms show on the RAM bar as ``other``.

A task of one line is given to every agent, each working it alone. A task of several lines is a queue: each line is
one task, and an agent takes the next one when it finishes. When an agent finishes a task it posts what it did to
the board, and the others read the newest posts before their next task.

The agents take turns on the one model (each step holds the model lock), so a swarm on one Mac is a study of
memory and contention, not of speed. Per agent the swarm counts tokens read and written, tasks done, and the time it
spent thinking and in tools, and it keeps spans and memory ticks on one clock for the channel rows.
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Callable

from camr_engine.agentic.brain import Brain
from camr_engine.agentic.gate import Gate
from camr_engine.agentic.loop import Run, ticks
from camr_engine.agentic.personas import Persona
from camr_engine.agentic.tools import Toolbox

MAX_AGENTS = 8
MAX_TASKS = 64
STEPS = 8
BOARD = 4  # the newest posts an agent reads before a task
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def tasks(text: str) -> list[str]:
    """The tasks in what a person typed: one per line, bullets and numbers dropped."""
    out = [_BULLET.sub("", line).strip() for line in (text or "").splitlines()]
    return [x for x in out if x][:MAX_TASKS]


class Agent:
    def __init__(self, i: int, brain: Brain):
        self.i, self.label, self.name = i, f"A{i}", f"swarm-a{i}"
        self.brain = brain
        self.state = "idle"  # idle, thinking, tool, waiting, measuring, done, stopped, failed
        self.task: str | None = None
        self.done = 0
        self.failed = 0
        self.tokens = {"prompt": 0, "written": 0}
        self.busy_s = {"model": 0.0, "tool": 0.0}
        self.steps = 0
        self.reads = {"ssd": 0, "ram": 0, "vault": 0, "bytes": 0}
        self.used = 0
        self.spans: list[dict] = []  # {t0, t1, kind: model|tool, label}
        self.ticks: list[dict] = []  # {t, kind: ssd|ram|vault|words|used}
        self.runs: list[str] = []
        self.last: dict | None = None  # the newest step's memory
        self.answers: list[dict] = []
        self.error: str | None = None
        self.run: Run | None = None
        self.well: dict | None = None  # its own reach's rooms, as of its last step

    def show(self) -> dict:
        st = self.run.state if self.run is not None and self.run.live else self.state
        return {"label": self.label, "name": self.name, "reach": f"agent:{self.name}", "state": st,
                "task": self.task, "done": self.done, "failed": self.failed, "tokens": dict(self.tokens),
                "busy_s": {k: round(v, 3) for k, v in self.busy_s.items()}, "steps": self.steps,
                "reads": dict(self.reads), "used": self.used, "spans": self.spans[-400:],
                "ticks": self.ticks[-1200:], "runs": self.runs[-20:], "last": self.last,
                "answers": self.answers[-8:], "error": self.error, "model": self.brain.label,
                "memory": self.brain.memory_on, "run": self.run.id if self.run is not None else None}


class Swarm:
    def __init__(self, sid: str, task: str, n: int, *, brains: Callable[[int], Brain],
                 toolbox: Callable[[Agent], Toolbox], persona: Persona, gate: Gate,
                 model_lock: threading.Lock | None = None, workspace: str = "", skills: str = "", marks=None,
                 pool=None, max_steps: int = STEPS, measuring: Callable[[], dict | None] | None = None):
        n = max(1, min(int(n), MAX_AGENTS))
        items = tasks(task)
        if not items:
            raise ValueError("give the swarm a task")
        self.id, self.text, self.persona, self.gate = sid, task.strip(), persona, gate
        self.model_lock = model_lock or threading.Lock()
        self.workspace, self.skills, self.marks, self.pool = workspace, skills, marks, pool
        self.max_steps, self.measuring = max_steps, measuring
        self.toolbox = toolbox
        self.mode = "same" if len(items) == 1 else "queue"
        self.queue: deque[str] = deque(items)
        self.each: dict[int, str] = {i: items[0] for i in range(1, n + 1)} if self.mode == "same" else {}
        self.total = n if self.mode == "same" else len(items)
        self.agents: list[Agent] = []
        try:
            for i in range(1, n + 1):
                self.agents.append(Agent(i, brains(i)))
        except BaseException:
            for a in self.agents:
                a.brain.close()
            raise
        self.board: list[dict] = []
        self.ram: list[dict] = []
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.started = time.time()
        self.ended: float | None = None
        self._t0 = time.perf_counter()
        self._end: float | None = None
        self.threads: list[threading.Thread] = []
        self._owners = self._tiers_owners()
        for a in self.agents:
            self._look(a)

    def now(self) -> float:
        """Seconds since the swarm started (the channel rows' clock); it stops when the swarm ends."""
        return round((self._end if self._end is not None else time.perf_counter()) - self._t0, 4)

    # -- running

    def start(self) -> Swarm:
        for a in self.agents:
            th = threading.Thread(target=self._agent, args=(a,), name=f"swarm-{self.id}-{a.label}", daemon=True)
            self.threads.append(th)
            th.start()
        threading.Thread(target=self._end_when_done, daemon=True).start()
        return self

    def stop(self) -> None:
        self.cancel.set()
        for a in self.agents:
            if a.run is not None:
                a.run.stop()

    @property
    def live(self) -> bool:
        return self.ended is None

    def _next(self, a: Agent) -> str | None:
        with self.lock:
            if self.mode == "same":
                return self.each.pop(a.i, None)
            return self.queue.popleft() if self.queue else None

    def _agent(self, a: Agent) -> None:
        k = 0
        while not self.cancel.is_set():
            task = self._next(a)
            if task is None:
                break
            k += 1
            a.task, a.state = task, "thinking"
            with self.lock:
                notes = [f"{m['from']} finished: {m['text']}" for m in self.board if m["from"] != a.label][-BOARD:]
            run = Run(f"{self.id}-{a.label}-{k}", task, brain=a.brain, tools=self.toolbox(a), persona=self.persona,
                      gate=self.gate, model_lock=self.model_lock, label=a.label, workspace=self.workspace,
                      skills=self.skills, marks=self.marks, notes=notes, notes_title="The other agents posted:",
                      max_steps=self.max_steps,
                      measuring=self.measuring, on_step=lambda r, turn, a=a: self._seen(a, r, turn),
                      on_think=lambda r, thought, a=a: self._look(a))
            a.run = run
            a.runs.append(run.id)
            run.execute()
            if run.state == "done":
                a.done += 1
                text = " ".join((run.answer or "").split())[:240]
                a.answers.append({"task": task, "answer": run.answer, "t": self.now()})
                with self.lock:
                    self.board.append({"from": a.label, "to": "all", "t": self.now(), "text": text, "task": task})
            elif run.state == "failed":
                a.failed += 1
                a.error = run.error
            a.state = run.state if run.state in ("stopped", "failed") else "idle"
        a.task = None
        if a.state not in ("failed",):
            a.state = "stopped" if self.cancel.is_set() else "done"

    def _end_when_done(self) -> None:
        for th in self.threads:
            th.join()
        self._sample()
        self._end = time.perf_counter()
        self.ended = time.time()

    def _seen(self, a: Agent, run: Run, turn: dict) -> None:
        """Count one step of an agent's run, on the swarm's clock."""
        t1 = self.now()
        if turn["kind"] == "model":
            dur = float(turn.get("total_s") or 0.0)
            t0 = max(0.0, t1 - dur)
            a.steps += 1
            a.tokens["prompt"] += int(turn.get("prompt_tokens") or 0)
            a.tokens["written"] += int(turn.get("written_tokens") or 0)
            a.busy_s["model"] += dur
            a.spans.append({"t0": round(t0, 4), "t1": t1, "kind": "model", "label": f"step {turn['step']}"})
            m = turn.get("memory")
            if m:
                a.last = {k: m.get(k) for k in ("reach", "room", "tier", "read_bytes", "nodes", "used", "closest",
                                                 "seconds", "gbps")}
                tier = m.get("tier")
                if tier in a.reads:
                    a.reads[tier] += 1
                a.reads["bytes"] += int(m.get("read_bytes") or 0)
                a.used += len(m.get("used") or [])
                from camr_engine.agentic.brain import Thought

                th = Thought("", [], float(turn.get("first_s") or 0.0), dur, 0, 0, None, m)
                a.ticks.extend(ticks(th, t0))
        elif turn["kind"] == "call":
            dur = float(turn.get("ms") or 0.0) / 1000
            a.busy_s["tool"] += dur
            a.spans.append({"t0": round(max(0.0, t1 - dur), 4), "t1": t1, "kind": "tool", "label": turn["tool"],
                            "ok": turn.get("ok"), "decision": (turn.get("ask") or {}).get("decision")})

    def _look(self, a: Agent) -> None:
        """Right after a step, while the model lock is held: the agent's well and the shared RAM, read while
        nothing changes them."""
        try:
            own = [r for r in a.brain.reaches() if r.get("kind") == "agent"]
        except Exception:  # noqa: BLE001 (the well keeps its last picture)
            own = None
        if own is not None:
            a.well = own[0] if own else None
        self._sample()

    # -- the shared RAM bar

    def _tiers_owners(self) -> dict[int, str]:
        """Which agent each memory's tiers belong to ("shared" for a reach several agents read)."""
        owner: dict[int, str] = {}
        for a in self.agents:
            session = getattr(a.brain, "session", None)
            for m in getattr(session, "memories", {}).values():
                t = getattr(m, "tiers", None)
                if t is not None:
                    owner[id(t)] = "shared" if id(t) in owner and owner[id(t)] != a.label else a.label
        return owner

    def _sample(self) -> None:
        """One sample of the shared RAM budget: how much each agent's hot rooms hold now."""
        p = self.pool
        if p is None:
            return
        by: dict[str, int] = {}
        rooms: dict[str, int] = {}
        try:
            sizes = list(p.sizes.items())
        except RuntimeError:  # changed while read: the next step samples again
            return
        for key, size in sizes:
            label = self._owners.get(id(key[0]), "other")
            by[label] = by.get(label, 0) + int(size)
            rooms[label] = rooms.get(label, 0) + 1
        s = {"t": self.now(), "budget": int(p.budget), "used": int(p.used_bytes()), "core": int(p.core_bytes),
             "by": by, "rooms": rooms}
        with self.lock:
            if not self.ram or {k: v for k, v in self.ram[-1].items() if k != "t"} != {k: v for k, v in s.items()
                                                                                         if k != "t"}:
                self.ram.append(s)
                del self.ram[:-600]

    # -- the page's view

    def snapshot(self) -> dict:
        wells = [{"label": a.label, "reach": a.well} for a in self.agents]
        with self.lock:
            board, ram = list(self.board), list(self.ram)
        return {"id": self.id, "task": self.text, "mode": self.mode, "total": self.total,
                "done": sum(a.done for a in self.agents), "persona": self.persona.id,
                "started": self.started, "ended": self.ended, "elapsed_s": round((self.ended or time.time())
                                                                                 - self.started, 2),
                "now": self.now(), "live": self.live, "agents": [a.show() for a in self.agents], "wells": wells,
                "board": board[-100:], "ram": ram[-600:], "queue": len(self.queue),
                "waiting": [w for w in self.gate.waiting() if w["owner"].startswith(f"{self.id}-")]}

    def close(self) -> None:
        self.stop()
        for th in self.threads:
            th.join(timeout=5)
        for a in self.agents:
            try:
                a.brain.close()
            except Exception:  # noqa: BLE001
                pass
