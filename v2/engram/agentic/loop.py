"""One task, step by step. Each step the model reads the task and everything done so far, and either calls tools
(their results come back next step) or answers in plain words, which ends the run. A run also ends when it is
stopped, after ``max_steps``, or on an error.

The model runs one step at a time under the app's model lock, so a chat answer, a code run and the agents of a swarm
take turns on the one GPU. While a benchmark measures, a run waits before its next step.

What a run keeps, for the page:
- ``turns``: the transcript (the task, each step's words and memory, each call with its result);
- ``trace``: spans on one clock (``model``, one track per tool, ``shell``), with memory ticks inside model spans;
- ``term``: what approved commands printed, for the read-only terminal (its last TERM_CHARS characters);
- ``wrote``: the files written, with their memory-gutter marks.

With memory on, a run that ends with an answer is remembered in the reach its persona writes to: the task, the files
written, the names they define, and the answer, so a later task can lean on it. Until that is kept the run is
``keeping``, which counts as running: the page keeps watching, and its memory stays open.

What the model reads of earlier steps is held to HISTORY_CHARS: the newest results in full, older ones shortened,
and more of them shortened, oldest first, until it fits, so a prompt stays well inside the reader's window.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Callable

from engram.agentic import marks as gutter
from engram.agentic.brain import Brain, Prompt, Thought
from engram.agentic.gate import Gate
from engram.agentic.parse import calls, prose
from engram.agentic.personas import Persona
from engram.agentic.tools import Done, Toolbox, short

MAX_STEPS = 12
STEP_TOKENS = 768
FULL_RESULTS = 6  # the newest results the model reads in full; older ones shortened
SHORT_RESULT = 240  # characters of a shortened result
HISTORY_CHARS = 60_000  # the steps so far, at most: about 15-20K tokens, well inside Qwen3's 40,960
TERM_CHARS = 200_000  # terminal characters kept (as engram.agentic.shell.KEEP)
TERM_LIMIT = 4000  # terminal chunks kept
ENDED = ("done", "stopped", "failed")

RULES = """You work in the folder "{ws}" on the user's Mac. Paths are relative to it.
Call tools as the tool list says; one reply may call several. Read a file before you change it. edit_file replaces
text copied exactly from the file; write_file writes a whole file.
run_shell and the MCP tools wait for the user to allow each call, and the user may refuse.
When the task is done, reply in plain words with what you did, and call no tool."""

_DEFINES = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|const|let|var|fn|func|struct|type)\s+"
                      r"([A-Za-z_][A-Za-z0-9_]*)", re.M)


class Run:
    def __init__(self, rid: str, task: str, *, brain: Brain, tools: Toolbox, persona: Persona, gate: Gate,
                 model_lock: threading.Lock | None = None, label: str = "", workspace: str = "",
                 skills: str = "", marks: gutter.Marks | None = None, notes: list[str] | None = None,
                 notes_title: str = "Since your last task, the user said:",
                 max_steps: int = MAX_STEPS, step_tokens: int = STEP_TOKENS, keep: bool = True,
                 measuring: Callable[[], dict | None] | None = None, on_step: Callable[[Run, dict], None] | None = None,
                 on_think: Callable[[Run, Thought], None] | None = None):
        self.id, self.task = rid, task
        self.brain, self.tools, self.persona, self.gate = brain, tools, persona, gate
        self.model_lock = model_lock or threading.Lock()
        self.label, self.workspace, self.skills, self.marks = label, workspace, skills, marks
        self.notes, self.notes_title = list(notes or []), notes_title
        self.max_steps, self.step_tokens, self.keep_it = max_steps, step_tokens, keep
        self.measuring, self.on_step, self.on_think = measuring, on_step, on_think
        self.state = "queued"  # queued, thinking, tool, waiting, measuring, keeping, done, stopped, failed
        self.answer: str | None = None
        self.error: str | None = None
        self.turns: list[dict] = [{"kind": "you", "text": task, "at": time.time()}]
        self.trace: list[dict] = []
        self.term: list[str] = []
        self.term_dropped = 0  # chunks left out from the start
        self.term_cut = 0  # characters left out from the start
        self._term_size = 0
        self.wrote: list[dict] = []
        self.history: list[tuple[str, dict, Done]] = []
        self.kept: dict | None = None
        self.tokens = {"prompt": 0, "written": 0}
        self.steps = 0
        self.started = time.time()
        self.ended: float | None = None
        self._t0 = time.perf_counter()
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None  # where it runs
        self.thread_id: str | None = None  # the Code screen's thread it belongs to

    # -- control

    def now(self) -> float:
        """Seconds since the run started, the trace's clock."""
        return round(time.perf_counter() - self._t0, 4)

    def start(self) -> Run:
        self.thread = threading.Thread(target=self.execute, name=f"run-{self.id}", daemon=True)
        self.thread.start()
        return self

    def stop(self) -> None:
        self.cancel.set()
        self.gate.cancel(self.id)

    @property
    def live(self) -> bool:
        return self.state not in ENDED

    def execute(self) -> None:
        try:
            self._loop()
        except Exception as e:  # noqa: BLE001 (shown in the transcript)
            self.error = f"{type(e).__name__}: {e}"[:600]
            self._set("failed")
            self._turn({"kind": "error", "text": self.error})
        finally:
            self.ended = time.time()
            self.gate.cancel(self.id)

    # -- the loop

    def _loop(self) -> None:
        for k in range(1, self.max_steps + 1):
            if self.cancel.is_set():
                break
            self._wait_measuring()
            if self.cancel.is_set():
                break
            p = self.prompt(k)
            self._set("thinking")
            t0 = self.now()
            with self.model_lock:
                if self.cancel.is_set():
                    break
                thought = self.brain.think(p)
                if self.on_think is not None:  # still holding the model: memory is not changing under it
                    self.on_think(self, thought)
            t1 = self.now()
            self.steps = k
            self.tokens["prompt"] += thought.prompt_tokens
            self.tokens["written"] += thought.gen_tokens
            found = calls(thought.text, known=self.tools.names())
            words = prose(thought.text)
            turn = {"kind": "model", "step": k, "text": words, "calls": [c.name for c in found],
                    "first_s": round(thought.first_s, 4), "total_s": round(thought.total_s, 4),
                    "prompt_tokens": thought.prompt_tokens, "written_tokens": thought.gen_tokens,
                    "decode_tps": thought.decode_tps, "memory": thought.memory}
            self._turn(turn)
            self._span("model", t0, t1, f"step {k}", ticks=ticks(thought, t0))
            if not found:
                self.answer = words or "(the model wrote nothing)"
                self._turn({"kind": "answer", "text": self.answer})
                self._set(self._answered())
                break
            for c in found:
                if self.cancel.is_set():
                    break
                self._set("tool")
                t2 = self.now()
                done = self.tools.run(c.name, c.args, owner=self.id, label=self.label, cancel=self.cancel,
                                      on_output=self._term, on_wait=lambda what: self._set("waiting"))
                t3 = self.now()
                self.history.append((c.name, c.args, done))
                call = {"kind": "call", "step": k, **done.show()}
                if done.wrote is not None and self.marks is not None:
                    new = gutter.leaning(thought.text, thought.pieces, thought.memory, c.start, c.end, done.content,
                                         c.form)
                    if new:  # the step's path strip, for the gutter's hover
                        strip = path_strip(thought)
                        for m in new.values():
                            m["strip"] = strip
                    got = self.marks.wrote(done.wrote.path, done.wrote.before, done.wrote.after, new, done.offset)
                    call["marks"] = {str(n): m for n, m in got["lines"].items()}
                    self.wrote.append({"path": done.wrote.path, "step": k, "lines": len(new)})
                self._turn(call)
                track = "shell" if c.name == "run_shell" else c.name
                self._span(track, t2, t3, short(c.args, 60), ok=done.ok, waited=bool(done.ask),
                           decision=done.ask["decision"] if done.ask else None)
                self._set("thinking")
        else:
            self.answer = f"stopped after {self.max_steps} steps without a final answer"
            self._turn({"kind": "answer", "text": self.answer, "cut": True})
            self._set(self._answered())
        if self.cancel.is_set() and self.state not in ("done", "keeping"):
            self._set("stopped")
            self._turn({"kind": "stopped", "text": "stopped"})
        if self.state == "keeping":
            try:
                with self.model_lock:  # remembering reads the moment with the model
                    self.kept = self.brain.keep(self.summary())
            except Exception as e:  # noqa: BLE001 (the answer stands; the page shows why it was not kept)
                self._turn({"kind": "error", "text": f"not kept in memory: {type(e).__name__}: {e}"[:600]})
            else:
                if self.kept:
                    self._turn({"kind": "kept", **self.kept})
            self._set("done")

    def _answered(self) -> str:
        """The state once the model answered: keeping it in memory first, when that is on."""
        return "keeping" if self.keep_it and self.brain.memory_on else "done"

    def _wait_measuring(self) -> None:
        while self.measuring is not None and self.measuring() and not self.cancel.is_set():
            self._set("measuring")
            self.cancel.wait(1.0)

    # -- what the model reads

    def system(self) -> str:
        text = f"{self.persona.system}\n\n{RULES.format(ws=self.workspace or 'none chosen')}"
        if self.skills:
            text += f"\nSkills you can read with load_skill:\n{self.skills}"
        return text

    def prompt(self, step: int) -> Prompt:
        lines = [f"Task: {self.task}"]
        if self.notes:
            lines += ["", self.notes_title, *[f"- {n}" for n in self.notes]]
        if self.history:
            lines += ["", "What you did so far, oldest first:"]
            for i, (name, args, done), body in zip(range(1, len(self.history) + 1), self.history, self._bodies()):
                lines += [f"[{i}] {name}({short(args)})", ("result:" if done.ok else "failed:"), body]
            lines += ["", "Next: call the next tool, or, when the task is done, answer in plain words with no tool "
                      "call."]
        return Prompt(self.system(), "\n".join(lines), self.tools.specs(), ask=self.task,
                      max_tokens=self.step_tokens, tags={"run": self.id, "step": step, **(
                          {"agent": self.label} if self.label else {})})

    def _bodies(self) -> list[str]:
        """Each result as the model reads it back: the newest FULL_RESULTS in full, older ones shortened; then, while
        they are longer than HISTORY_CHARS together, the oldest full ones shortened too (the newest one stays whole,
        and is cut only when it alone is too long)."""
        n = len(self.history)
        bodies = [done.text if i >= n - FULL_RESULTS else _shorten(done.text, SHORT_RESULT)
                  for i, (_, _, done) in enumerate(self.history)]
        size = sum(len(b) for b in bodies)
        for i in range(n - 1):
            if size <= HISTORY_CHARS:
                break
            short_ = _shorten(bodies[i], SHORT_RESULT)
            size -= len(bodies[i]) - len(short_)
            bodies[i] = short_
        if size > HISTORY_CHARS and bodies:
            room = max(SHORT_RESULT, HISTORY_CHARS - (size - len(bodies[-1])))
            if len(bodies[-1]) > room:
                bodies[-1] = bodies[-1][:room] + f"\n… {len(bodies[-1]) - room:,} more characters left out"
        return bodies

    def summary(self) -> str:
        """What is remembered of the run: the task, the files, the names they define, and the answer."""
        files = list(dict.fromkeys(w["path"] for w in self.wrote))
        names = []
        for _, _, done in self.history:
            if done.wrote is not None:
                names += _DEFINES.findall(done.content)
        names = list(dict.fromkeys(names))[:24]
        text = f"Code task: {self.task.strip()[:300]}"
        if files:
            text += f" Files written: {', '.join(files[:12])}."
        if names:
            text += f" Names defined: {', '.join(names)}."
        if self.answer:
            text += f" Outcome: {self.answer.strip()[:400]}"
        return " ".join(text.split())

    # -- keeping the page's view

    def _set(self, state: str) -> None:
        with self.lock:
            self.state = state

    def _turn(self, turn: dict) -> None:
        turn.setdefault("at", time.time())
        with self.lock:
            self.turns.append(turn)
        if self.on_step is not None:
            try:
                self.on_step(self, turn)
            except Exception:  # noqa: BLE001 (a watcher never stops the run)
                pass

    def _span(self, track: str, t0: float, t1: float, label: str, **more) -> None:
        with self.lock:
            self.trace.append({"track": track, "t0": t0, "t1": t1, "label": label, **more})

    def _term(self, chunk: str) -> None:
        """Keep a piece of terminal output: the last TERM_CHARS characters (and TERM_LIMIT pieces) at most."""
        with self.lock:
            self.term.append(chunk)
            self._term_size += len(chunk)
            if self._term_size <= TERM_CHARS and len(self.term) <= TERM_LIMIT:
                return
            k, size = 0, self._term_size
            while k < len(self.term) - 1 and (size > TERM_CHARS or len(self.term) - k > TERM_LIMIT):
                size -= len(self.term[k])
                k += 1
            self.term_cut += self._term_size - size
            self._term_size = size
            del self.term[:k]
            self.term_dropped += k

    def snapshot(self, term_after: int = 0, turns_after: int = 0) -> dict:
        """The run for the page. ``term_after`` and ``turns_after`` are how many terminal chunks and turns the page
        has already (turns are only ever added, so the page appends the rest)."""
        with self.lock:
            start = max(0, term_after - self.term_dropped)
            turns_after = max(0, min(turns_after, len(self.turns)))
            return {"id": self.id, "task": self.task, "state": self.state, "answer": self.answer, "error": self.error,
                    "persona": self.persona.id, "label": self.label, "memory": self.brain.memory_on,
                    "model": self.brain.label, "steps": self.steps, "max_steps": self.max_steps,
                    "tokens": dict(self.tokens), "started": self.started, "ended": self.ended,
                    "elapsed_s": round((self.ended or time.time()) - self.started, 2),
                    "turns": self.turns[turns_after:], "turns_from": turns_after, "turns_total": len(self.turns),
                    "trace": list(self.trace),
                    "term": self.term[start:], "term_next": self.term_dropped + len(self.term),
                    "term_cut": self.term_cut, "wrote": list(self.wrote), "kept": self.kept,
                    "waiting": self.gate.waiting(self.id)}


def _shorten(text: str, limit: int) -> str:
    one = " ".join(text.split())
    return one if len(one) <= limit else one[:limit] + "…"


def path_strip(thought: Thought) -> dict:
    """A step's path strip, small enough to keep with each gutter mark: where the room came from, how long each part
    of the wait took, how much was used, and the first word and total times."""
    m = thought.memory or {}
    return {"tier": m.get("tier"), "seconds": {k: round(float(v), 4) for k, v in (m.get("seconds") or {}).items()},
            "read_bytes": m.get("read_bytes"), "gbps": m.get("gbps"), "used": len(m.get("used") or []),
            "picked": len(m.get("nodes") or []), "first_s": round(thought.first_s, 4),
            "total_s": round(thought.total_s, 4)}


def ticks(thought: Thought, t0: float) -> list[dict]:
    """Memory ticks inside a model span, on the run's clock: the read (blue for the SSD, amber for a RAM hit,
    violet for words), then a green tick at each written word that leaned on a used moment."""
    m = thought.memory
    if not m:
        return []
    sec = m.get("seconds") or {}
    at = t0 + sec.get("choose", 0) + sec.get("core", 0)
    out = []
    if m.get("tier") == "ssd":
        out.append({"t": round(at, 4), "kind": "ssd", "bytes": m.get("read_bytes"), "s": sec.get("fetch")})
    elif m.get("tier") == "ram":
        out.append({"t": round(at, 4), "kind": "ram"})
    elif m.get("tier") == "vault" or m.get("asleep"):
        out.append({"t": round(at, 4), "kind": "vault"})
    if m.get("closest"):
        out.append({"t": round(at + sec.get("fetch", 0), 4), "kind": "words", "n": len(m["closest"])})
    lean = m.get("lean") or []
    if lean:
        span = max(thought.total_s - thought.first_s, 0.0)
        step = span / max(len(lean), 1)
        used = set(m.get("used") or [])
        for i, (node, look) in enumerate(lean):
            if node is not None and look >= gutter.USED and node in used:
                out.append({"t": round(t0 + thought.first_s + i * step, 4), "kind": "used", "look": look})
    return out[:400]
