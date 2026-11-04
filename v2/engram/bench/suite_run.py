"""The Hugging Face suites for Ollama (paired or bare) and for Claude with no memory (engram.bench.claude).

  babilong          qa1-qa5 at 4k, 16k, 64k and 128k, plus 512k and 1M for Claude: the story is told in chunks of
                    about 512 tokens, then its question is asked
  memoryagentbench  Conflict_Resolution: each context's chunks in order, then its questions
  math500           50 problems of levels 3-5, no memory: a capability baseline
  aime              AIME 2025 and 2026, no memory
  harp              correction pairs, memory on and memory off. On: problem A and its worked solution are told as a
                    correction, then 30K tokens of Long Haul noise; then problem B (same subject and level) is asked,
                    and A again. Off: B and A are asked with nothing told.

    python -m engram.bench.suite_run babilong --contender ollama-bare:qwen3:1.7b --n 3 --lengths 4k
    python -m engram.bench.suite_run harp --contender ollama:qwen3-1.7b --n 20
    python -m engram.bench.suite_run math500 --contender claude-haiku-5-5 --n 50 --max-usd 10
    python -m engram.bench.suite_run math500 --contender claude-haiku-5-5 --resume records/bench/<day>/<file>.json

The local contenders (engine:, words:, bare:) are refused here for now. engram.bench.local words them for the Long
Haul: the engine and words are told to answer in one sentence from their notes or say "I don't know", and bare is told
the story is a project's history. On a maths baseline or a BABILong story, that would test those words rather than
the model. They can run once engram.bench.local takes a suite's wording.

Every contender here reads the suite's own wording, with no instructions of its own: what was told goes inside
<context>...</context> (bare Ollama's system message, the front of Claude's user message), or comes back from the
pairing's memory as notes; then the question. Each record's ``contender`` holds that wording (``system``, ``frame``,
``prompt``).

Each context gets a memory of its own, in a new folder under work/memories/. Every answer is graded by its suite's
own rule; a question that fails is recorded with verdict "error" and is not graded. An answer cut off by its limit
(Ollama's done_reason "length", Claude's stop_reason "max_tokens") is graded as it stands and counted as
``truncated``. The record is written again after every context, to records/bench/<YYYY-MM-DD>/<HHMMSS>-<suite>-
<contender>.json. It holds the answers and their metrics, a summary per family (and by length, mode or level), and the
environment. BABILong's ``all`` takes every length run. Its ``shared`` block takes only 4k to 128k, which every
contender is run at, so it is the one to compare across contenders.

A context that fails to open or be told is recorded with outcome "error", and the run goes on. Three in a row stop it,
and ``stopped`` says why. ``planned_groups`` is written at the start. ``complete`` turns true only when every planned
context was run to its end with no failed question. ``--resume <record>`` runs what a stopped or crashed run left.
The contexts it finished are kept and skipped. The rest are added to the same record: those that failed, had a failed
question, were stopped, or never started.

A question's family is its suite's name, so no contender adds a Long Haul hint on the form of the answer (each suite
says how to answer). The reply limits are the shared ones: 400 tokens for the maths suites, 120 for the rest.

Claude goes through engram.bench.claude, so every call is held in its ledger against the night's cap. Before a Claude
run the cost is estimated and printed, and a run whose expected cost passes ``--max-usd`` (10 by default) does not
start. What the run has spent is read from the ledger: every try of every call, a failed or retried one too. Each try
is sent only when its worst case still fits under ``--max-usd`` with that, so the run stops before it could pass it.
``--max-usd`` holds for each invocation; a resumed record keeps what the earlier ones spent. Claude keeps the
yardstick's settings (effort medium, adaptive thinking), so each reply gets its limit plus ``--think-room`` tokens to
think in.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Sequence

from engram.bench.contender import (MAX_TOKENS, OTHER_TOKENS, RECORDS, THINKING, Answer, Contender, environment,
                                    grade_with, max_tokens, metrics, record_path, slug, summarize, write_record)
from engram.bench.ollama_run import HAUL, MEMORIES, PROXY_PORT, SUITE, Frame, counter

SUITES = ("babilong", "memoryagentbench", "math500", "aime", "harp")
LENGTHS = ("4k", "16k", "64k", "128k")  # every contender runs these: BABILong's ``shared`` summary is over them
BIG_LENGTHS = ("512k", "1M")  # for Claude only
TELL_TOKENS = 512  # a BABILong story is told in chunks of about this many tokens
NOISE_TOKENS = 30_000
DEFAULT_N = {"babilong": 5, "memoryagentbench": 10, "math500": 50, "aime": None, "harp": 30}
LEVELS = (3, 4, 5)
LIMITS = {"babilong": max_tokens(None), "memoryagentbench": max_tokens(None), "math500": max_tokens("maths"),
          "aime": max_tokens("maths"), "harp": max_tokens("maths")}
CORRECTION = "Keep this worked solution: it shows how to solve problems like it.\n\n"
KEYS = {"babilong": ("length", "task"), "memoryagentbench": ("source",), "math500": ("level",), "aime": ("year",),
        "harp": ("mode", "ask", "mode_ask")}
MAX_FAILED = 3  # contexts in a row that fail to open or be told before the run stops
LOCAL_KINDS = ("engine:", "words:", "bare:")
LOCAL_REFUSED = ("the local contenders (engine:, words:, bare:) are not run on the suites yet: engram.bench.local "
                 "gives them the Long Haul's wording (answer from the notes or the project's history only, else \"I "
                 "don't know\"), which would make a capability baseline a test of that wording. Use ollama:, "
                 "ollama-bare: or claude-, or give engram.bench.local a suite's wording first.")

THINK_ROOM = 8_192  # Claude thinks before it answers (it cannot be turned off on Opus): room for that
CLAUDE_WINDOW = 1_000_000
CLAUDE_MARGIN = 10_000
FIT_TRIES = 6
CHARS_PER_TOKEN = 3.0  # for the cost estimate before a run (BABILong 4k measured 3.1 on Haiku 5.5)
SAFE_CHARS_PER_TOKEN = 2.0  # for a prompt that is not counted: an over-count only holds a little more in the ledger
EXPECTED_THINKING = {"math500": 3_000, "aime": 6_000, "harp": 3_000}  # thinking a reply is expected to use
OTHER_THINKING = 300
SETTINGS_FREE = ("estimate", "max_usd", "think_room")  # settings a resumed run may change


class StopRun(RuntimeError):
    """The run stops here: the next call could pass a budget, so it was not sent."""


# --- what is told and asked ---------------------------------------------------------------------------------------


@dataclass
class Ask:
    """One question: its prompt, the right answer, its family and reply limit, and how to grade a reply."""

    id: str
    prompt: str
    expected: Any
    family: str
    grade: Callable[[str], Any]
    meta: dict = field(default_factory=dict)

    @property
    def limit(self) -> int:
        return LIMITS.get(self.family, max_tokens(self.family))


@dataclass
class Group:
    """Questions on one context: a new memory is opened, ``tells`` are told in order, then ``asks`` are asked."""

    id: str
    tells: list[str]
    asks: list[Ask]
    meta: dict = field(default_factory=dict)


def plan_babilong(n: int, seed: int = 0, lengths: Sequence[str] = LENGTHS, tasks: Sequence[str] | None = None, *,
                  store: Any = None) -> list[Group]:
    """``n`` stories per task, each at every length: the story in chunks, then its question without the context."""
    from engram.bench.suites import babilong
    from engram.bench.suites.common import chunk

    out = []
    for it in babilong.sample(n, seed, tasks or babilong.TASKS, lengths, store=store):
        meta = {"task": it.meta["task"], "length": it.meta["length"], "length_tokens": it.length_tokens}
        ask = Ask(it.id, babilong.prompt(it, with_context=False), it.answer, "babilong",
                  lambda reply, it=it: babilong.grade(it, reply), meta)
        out.append(Group(it.id, chunk(it.chunks[0], TELL_TOKENS), [ask], meta))
    return out


def plan_memoryagentbench(n: int, seed: int = 0, splits: Sequence[str] = ("Conflict_Resolution",),
                          **kw: Any) -> list[Group]:
    """``n`` questions per context: the context's chunks in order, then its questions."""
    from engram.bench.suites import memoryagentbench as mab

    groups: dict[tuple, Group] = {}
    for it in mab.sample(n, seed, tuple(splits), **kw):
        key = (it.meta["split"], it.meta["row"])
        if key not in groups:
            meta = {"split": key[0], "row": key[1], "source": it.meta["source"], "length_tokens": it.length_tokens}
            groups[key] = Group(f"mab/{mab.SHORT.get(key[0], key[0])}/{key[1]:02d}", list(it.chunks), [], meta)
        groups[key].asks.append(Ask(it.id, mab.prompt(it), it.answer, "memoryagentbench",
                                    lambda reply, it=it: mab.grade(it, reply),
                                    {"source": it.meta["source"], "kind": it.meta["kind"]}))
    return list(groups.values())


def plan_math500(n: int = 50, seed: int = 0, levels: Sequence[int] = LEVELS, *, path: Any = None) -> list[Group]:
    """``n`` problems of these levels, chosen by the seed, one at a time; nothing is told."""
    from engram.bench.suites import math500
    from engram.bench.suites.common import rng

    items = [it for it in math500.load(path=path) if int(it.meta["level"]) in set(levels)]
    picks = sorted(rng(seed, math500.NAME, "levels", *sorted(levels)).sample(range(len(items)), min(n, len(items))))
    return [Group(it.id, [], [Ask(it.id, math500.prompt(it), it.answer, "math500",
                                  lambda reply, it=it: math500.grade(it, reply),
                                  {"level": it.meta["level"], "subject": it.meta["subject"]})])
            for it in (items[k] for k in picks)]


def plan_aime(n: int | None = None, seed: int = 0, years: Sequence[int] = (2025, 2026), *,
              paths: dict | None = None) -> list[Group]:
    """Every problem of these years (or ``n`` a year, chosen by the seed), one at a time; nothing is told."""
    from engram.bench.suites import aime

    items = aime.load(tuple(years), paths=paths) if n is None else aime.sample(n, seed, tuple(years), paths=paths)
    return [Group(it.id, [], [Ask(it.id, aime.prompt(it), it.answer, "aime",
                                  lambda reply, it=it: aime.grade(it, reply), {"year": it.meta["year"]})])
            for it in items]


@lru_cache(maxsize=2)
def noise_pool(haul: str) -> tuple[tuple[str, int], ...]:
    """The Long Haul's noise, as (line, tokens): every event no probe needs, without day lines or the maths course."""
    from engram.bench.haul.script import load_events, load_probes
    from engram.bench.longhaul import line

    needed: set[int] = set()
    for p in load_probes(Path(haul)):
        needed.update(p.get("events") or [])
        if p.get("event") is not None:
            needed.add(p["event"])
    return tuple((line(e), int(e["tokens"])) for e in load_events(Path(haul))
                 if e["i"] not in needed and e["kind"] not in ("day", "maths"))


def noise(pool: Sequence[tuple[str, int]], tokens: int, seed: int, key: str) -> list[str]:
    """Consecutive noise events, at least ``tokens`` tokens of them, starting where the seed and key say."""
    if not pool or tokens <= 0:
        return []
    from engram.bench.suites.common import rng

    i, got, out = rng(seed, "harp-noise", key).randrange(len(pool)), 0, []
    while got < tokens and len(out) < len(pool):
        text, n = pool[i % len(pool)]
        out.append(text)
        got += n
        i += 1
    return out


def plan_harp(n: int, seed: int = 0, modes: Sequence[str] = ("on", "off"), *, noise_tokens: int = NOISE_TOKENS,
              haul: Path = HAUL, path: Any = None, pool: Sequence[tuple[str, int]] | None = None) -> list[Group]:
    """``n`` correction pairs, each run once per mode. On: A's correction and the noise are told, then B is asked,
    then A again. Off: B and A are asked with nothing told."""
    from engram.bench.suites import harp

    if "on" in modes and pool is None:
        pool = noise_pool(str(haul))
    out = []
    for it in harp.sample(n, seed, path=path):
        first = it.meta["first"]
        meta = {"subject": it.meta["subject"], "level": it.meta["level"], "a_id": first["id"], "b_id": it.meta["b_id"]}
        for mode in modes:
            tells = [CORRECTION + it.chunks[0], *noise(pool or (), noise_tokens, seed, it.id)] if mode == "on" else []
            asks = [Ask(f"{it.id}#{mode}/B", harp.prompt(it), it.answer, "harp",
                        lambda reply, it=it: harp.grade(it, reply),
                        {"mode": mode, "ask": "B", "mode_ask": f"{mode}/B"}),
                    Ask(f"{it.id}#{mode}/A", harp.prompt(it, first=True), first["answer"], "harp",
                        lambda reply, it=it: harp.grade_first(it, reply),
                        {"mode": mode, "ask": "A", "mode_ask": f"{mode}/A"})]
            out.append(Group(f"{it.id}#{mode}", tells, asks, {**meta, "mode": mode}))
    return out


# --- Claude, with no memory ---------------------------------------------------------------------------------------


class ClaudeContender(Contender):
    """Claude as a contender, with no memory: what was told is kept as text and goes before each question; when it
    does not fit the window, its most recent part does. Each question is one call through engram.bench.claude, so its
    ledger and the night's cap hold. A history asked more than once (``expect``) is marked for the cache.

    ``max_usd`` is this run's own cap. What the run has spent is the sum of its own ledger lines (its ``purpose`` is
    its own), so a try that failed or was retried counts too. This contender sends each try itself, and a try whose
    worst case could pass the cap is not sent (StopRun)."""

    def __init__(self, model: str, *, claude: Any = None, max_usd: float = 10.0, think_room: int = THINK_ROOM,
                 frame: Frame = SUITE, count: Callable[[str], int] | None = None, task: str = "suite"):
        from engram.bench.claude import check_model

        check_model(model)
        self.model, self.name, self.max_usd, self.think_room = model, model, max_usd, think_room
        self.frame, self.task = frame, task
        self.purpose = f"{task} [{model}] run {uuid.uuid4().hex[:8]}"  # this run's ledger lines, and only them
        self._claude, self._count = claude, count
        self.thinking = "adaptive"
        self.spent, self.replies_usd, self.calls, self.tries = 0.0, 0.0, 0, 0
        self.texts: list[str] = []
        self.history_tokens, self.reuse = 0, 1

    @property
    def claude(self) -> Any:
        if self._claude is None:
            from engram.bench.claude import Claude

            self._claude = Claude()
        return self._claude

    def count(self, text: str) -> int:
        if self._count is None:
            self._count, _ = counter(strict=False)  # only for history_tokens: the API counts every prompt
        return self._count(text)

    def _ledger_lines(self) -> Callable[[], list[dict]] | None:
        lines = getattr(getattr(self._claude, "ledger", None), "lines", None)
        return lines if callable(lines) else None

    def spent_now(self) -> float:
        """What this run has spent: its own ledger lines (every try's cost, and any hold still open). A stand-in
        Claude with no ledger lines counts its replies."""
        lines = self._ledger_lines()
        if lines is None:
            return self.replies_usd
        mine = [x for x in lines() if x.get("purpose") == self.purpose]
        closed = {x.get("hold") for x in mine if x.get("kind") != "hold"}
        return (sum(float(x.get("cost_usd") or 0.0) for x in mine)
                + sum(float(x.get("hold_usd") or 0.0) for x in mine
                      if x.get("kind") == "hold" and x.get("hold") not in closed))

    def open(self, folder: Path) -> None:
        self.texts, self.history_tokens, self.reuse = [], 0, 1

    def expect(self, asks: int) -> None:
        """How many questions will be asked on what is told next: more than one marks it for the cache."""
        self.reuse = asks

    def tell(self, text: str, day: int) -> None:
        self.texts.append(text)
        self.history_tokens += self.count(text)

    def _messages(self, start: int, question: str, cache: bool) -> list[dict]:
        content: list[dict] = []
        if start < len(self.texts):
            f = self.frame
            told = f.join.join(self.texts[start:])
            block: dict[str, Any] = {"type": "text", "text": f"{f.opener}{told}{f.closer}\n\n"}
            if cache:
                block["cache_control"] = {"type": "ephemeral"}
            content.append(block)
        content.append({"type": "text", "text": question})
        return [{"role": "user", "content": content}]

    def _fit(self, question: str, limit: int, cache: bool, purpose: str) -> tuple[int, int, list[dict]]:
        """(start, prompt tokens, messages): the most recent told texts that fit the window with the question and the
        reply. A short prompt is not counted: it is sized from its characters, on the high side, for the hold."""
        from engram.bench.claude import EFFORT, TOO_LONG, ClaudeError

        c = self.claude
        target = getattr(c, "window", CLAUDE_WINDOW) - limit - getattr(c, "margin", CLAUDE_MARGIN)
        tail = [0] * (len(self.texts) + 1)
        for i in range(len(self.texts) - 1, -1, -1):
            tail[i] = tail[i + 1] + len(self.texts[i]) + 1
        fixed = len(question) + len(self.frame.opener + self.frame.closer) + len(self.frame.system or "") + 2
        if (tail[0] + fixed) / CHARS_PER_TOKEN < 0.5 * target:
            return 0, math.ceil((tail[0] + fixed) / SAFE_CHARS_PER_TOKEN) + 64, self._messages(0, question, cache)
        start = 0
        for _ in range(FIT_TRIES):
            messages = self._messages(start, question, cache)
            try:
                n = c.count(self.model, messages, purpose + " (fit)", system=self.frame.system,
                            output_config={"effort": EFFORT})
            except ClaudeError as e:
                too_long = e.status.startswith("http_413") or (e.status.startswith("http_400")
                                                                and bool(TOO_LONG.search(e.detail or "")))
                if not too_long or start >= len(self.texts):
                    raise
                n = 2 * target
            if n <= target:
                return start, n, messages
            keep, nxt = tail[start] * target / n * 0.97, start
            while nxt < len(self.texts) and tail[nxt] > keep:
                nxt += 1
            start = max(start + 1, nxt)
        raise ClaudeError(f"{purpose}: no part of the history fits with the question", "no_room")

    def _send(self, messages: list[dict], limit: int, prompt_tokens: int, cache: bool, worst: float) -> Any:
        """One call, its tries sent one at a time by this contender (the client's own patience is set to none for
        each), so the run's cap is checked before every try with what the tries before it cost."""
        from engram.bench.claude import BudgetError, ClaudeError

        c = self.claude
        patience = getattr(c, "patience", None)
        tries = (patience or 0) + 1
        for attempt in range(1, tries + 1):
            spent = self.spent_now()
            if spent + worst > self.max_usd:
                raise StopRun(f"${spent:.4f} spent + ${worst:.4f} worst case would pass this run's "
                              f"${self.max_usd:.2f}")
            self.tries += 1
            if patience is not None:
                c.patience = 0
            try:
                return c.call(self.model, messages, max_tokens=limit, purpose=self.purpose, system=self.frame.system,
                              prompt_tokens=prompt_tokens, cache=cache)
            except BudgetError as e:  # the night's cap, held in the ledger
                raise StopRun(f"the ledger's cap: {e}") from e
            except ClaudeError as e:
                if not e.retryable or attempt >= tries:
                    raise
                wait = e.wait_s
            finally:
                if patience is not None:
                    c.patience = patience
                self.spent = self.spent_now()
            getattr(c, "sleep", time.sleep)(wait)
        raise AssertionError("unreachable")

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        from engram.bench.cost import estimate_usd

        limit = max_tokens + self.think_room
        cache = self.reuse > 1 and bool(self.texts)
        start, prompt_tokens, messages = self._fit(question, limit, cache, self.purpose)
        worst = estimate_usd(self.model, prompt_tokens, limit, "5m" if cache else None)
        call = self._send(messages, limit, prompt_tokens, cache, worst)
        self.calls += 1
        self.replies_usd += call.cost_usd
        self.spent = self.spent_now()
        t = call.tokens
        m = metrics(ttft_s=call.ttft_s, total_s=call.total_s, prefill_tps=None, decode_tps=call.output_tps,
                    retrieval_ms=None, bytes_read=None, gbps=None, read_share=None, context_tokens=t.prompt,
                    history_tokens=self.history_tokens, peak_ram_gb=None, disk_gb=None, tier=None)
        return Answer(call.text, m, {
            "cost_usd": round(call.cost_usd, 6), "input_tokens": t.input, "cache_read_tokens": t.cache_read,
            "cache_write_tokens": t.cache_write, "output_tokens": t.output, "thinking_tokens": t.thinking,
            "first_token_s": call.first_token_s, "stop_reason": call.stop_reason, "refused": call.refused,
            "answered_by": call.answered_by, "cut_from_front": start > 0, "claude_max_tokens": limit,
            "estimate_usd": round(call.estimate_usd, 6), "worst_usd": round(worst, 6)})

    def status(self) -> dict:
        return {"spent_usd": round(self.spent, 6), "calls": self.calls, "tries": self.tries}

    def describe(self) -> dict:
        from engram.bench.claude import EFFORT

        c = self._claude
        f = self.frame
        return {"name": self.name, "kind": "claude", "model": self.model, "memory": None, "effort": EFFORT,
                "thinking": self.thinking, "think_room": self.think_room, "max_usd": self.max_usd,
                "spent_usd": round(self.spent, 6), "replies_usd": round(self.replies_usd, 6),
                "spent_from": "ledger" if self._ledger_lines() is not None else "replies", "calls": self.calls,
                "tries": self.tries, "purpose": self.purpose, "system": f.system,
                "frame": {"opener": f.opener, "closer": f.closer, "lines_joined_by": f.join},
                "prompt": "user: what was told inside the opener and closer (its most recent part when it does not "
                          "fit), then the question; no system prompt",
                "ledger": str(c.ledger.path) if c is not None and hasattr(c, "ledger") else None}

    def close(self) -> None:
        self.texts = []


def estimate(groups: Sequence[Group], model: str, think_room: int = THINK_ROOM, window: int = CLAUDE_WINDOW) -> dict:
    """What a Claude run should cost, before it starts: prompts sized from their characters, a history asked more
    than once written to the cache once and read after, and the thinking each suite is expected to use. ``worst``
    is every allowed output token spent."""
    from engram.bench.cost import estimate_usd, rate

    expected = worst = 0.0
    calls = prompt_total = 0
    for g in groups:
        hist = min(window, sum(len(t) + 1 for t in g.tells) / CHARS_PER_TOKEN)
        cached = len(g.asks) > 1 and hist > 0
        for k, a in enumerate(g.asks):
            prompt = int(min(window, hist + len(a.prompt) / CHARS_PER_TOKEN + 64))
            r = rate(model, prompt)
            into = (hist * (r.cache_write_5m if k == 0 else r.cache_read) + (prompt - hist) * r.input) if cached \
                else prompt * r.input
            out = a.limit + min(think_room, EXPECTED_THINKING.get(a.family, OTHER_THINKING))
            expected += (into + out * r.output) / 1e6
            worst += estimate_usd(model, prompt, a.limit + think_room, "5m" if cached else None)
            calls += 1
            prompt_total += prompt
    return {"model": model, "calls": calls, "prompt_tokens": prompt_total, "expected_usd": round(expected, 4),
            "worst_usd": round(worst, 4)}


# --- contenders by name -------------------------------------------------------------------------------------------


def is_claude(name: str) -> bool:
    return name.startswith(("claude-", "claude:"))


def is_ollama(name: str) -> bool:
    return name.startswith(("ollama:", "ollama-bare:"))


def contender_name(name: str) -> str:
    """The name a contender made from ``name`` goes by, without making it (Ollama's models as Ollama names them)."""
    if is_claude(name):
        return name.removeprefix("claude:")
    from engram.bench.ollama_run import MODELS

    kind, _, model = name.partition(":")
    return f"{kind}:{MODELS.get(model, model)}"


def make_contender(name: str, *, max_usd: float = 10.0, think_room: int = THINK_ROOM, port: int = PROXY_PORT,
                   task: str = "suite", claude: Any = None) -> Contender:
    """A contender by name: ollama:<model>, ollama-bare:<model>, or claude-<model> (or claude:<model>). The local
    contenders are refused (LOCAL_REFUSED)."""
    if is_ollama(name):
        from engram.bench.ollama_run import make

        return make(name, frame=SUITE, **({"port": port} if name.startswith("ollama:") else {}))
    if is_claude(name):
        return ClaudeContender(name.removeprefix("claude:"), claude=claude, max_usd=max_usd, think_room=think_room,
                               task=task)
    if name.startswith(LOCAL_KINDS):
        raise ValueError(LOCAL_REFUSED)
    raise ValueError(f"no contender {name!r}: use ollama:<model>, ollama-bare:<model> or claude-<model>")


# --- running ------------------------------------------------------------------------------------------------------


def truncated(extra: dict, room: int) -> bool | None:
    """Whether a reply was cut off by its limit: Ollama's done_reason "length", Claude's stop_reason "max_tokens",
    else its own count of the tokens it wrote against its room (None when nothing says)."""
    if extra.get("done_reason") is not None:
        return extra["done_reason"] == "length"
    if extra.get("stop_reason") is not None:
        return extra["stop_reason"] == "max_tokens"
    n = extra.get("answer_tokens")
    return None if n is None else int(n) >= room


def ask_one(contender: Contender, ask: Ask, meta: dict) -> dict:
    """Ask, grade, and the answer's record, as the shared runner writes one. A question that fails is recorded with
    verdict "error" and right None (never graded), and the run goes on; a StopRun goes up to the runner."""
    room = ask.limit
    try:
        a = contender.ask(ask.prompt, max_tokens=room, family=ask.family)
        right, verdict, reason = grade_with(lambda _q, text: ask.grade(text), ask, a.text)
        out, m, extra = a.text, metrics(**a.metrics), a.extra
    except StopRun:
        raise
    except Exception as e:  # one failed question is recorded, not fatal
        right, verdict, reason, out, m, extra = None, "error", f"{type(e).__name__}: {e}"[:400], None, metrics(), {}
    return {"id": ask.id, "family": ask.family, "question": ask.prompt, "expected": ask.expected, "answer": out,
            "verdict": verdict, "right": right, "reason": reason, "max_tokens": room,
            "truncated": truncated(extra, room) if out is not None else None, "metrics": m, "extra": extra,
            **meta, **ask.meta}


def breakdown(answers: Sequence[dict], keys: Sequence[str], suite: str | None = None) -> dict:
    """The summary per family and for all, then ``by_<key>`` for each key an answer carries (length, mode, ...). For
    BABILong, ``lengths`` names the lengths ``all`` pools, and ``shared`` is the summary over LENGTHS only, which
    every contender runs."""
    out = summarize(list(answers))
    for key in keys:
        values: dict[str, list[dict]] = {}
        for a in answers:
            if a.get(key) is not None:
                values.setdefault(str(a[key]), []).append(a)
        out[f"by_{key}"] = {v: summarize(xs)["all"] for v, xs in values.items()}
    if suite == "babilong":
        order = LENGTHS + BIG_LENGTHS
        out["lengths"] = sorted({str(a["length"]) for a in answers if a.get("length") is not None},
                                key=lambda x: (order.index(x) if x in order else len(order), x))
        shared = [a for a in answers if a.get("length") in LENGTHS]
        out["shared"] = {"lengths": list(LENGTHS), **summarize(shared)["all"]}
    return out


def finished(group: dict) -> bool:
    """Whether a group in a record was run to its end with no failed question, so a resumed run skips it."""
    return (group.get("outcome", "ok") == "ok"
            and not any(a.get("verdict") == "error" for a in group.get("answers") or []))


def _folders(record: dict) -> set[str]:
    return {record.get("folder") or "", *((r.get("folder") or "") for r in record.get("resumes") or [])}


def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception as e:  # noqa: BLE001: a record is written whatever a contender's report does
        return {"error": f"{type(e).__name__}: {e}"[:200]} if default is None else default


def run(suite: str, contender: Contender, groups: Sequence[Group], *, settings: dict | None = None,
        records: Path = RECORDS, memories: Path = MEMORIES, progress: Callable[[str], None] = print,
        save: bool = True, resume: dict | None = None) -> dict:
    """Each group: a new memory, its tells in order, then its asks, each graded. The record is saved after every
    group. A group that fails to open or be told is recorded with outcome "error" and the run goes on. MAX_FAILED in
    a row end it, as a budget stop does, and ``stopped`` says why. ``complete`` is true only when every planned group
    was run to its end with no failed question.

    ``resume`` is an earlier record of this run (with its ``path``): the groups it finished are kept and skipped, and
    the rest are run and added to it, in its file. Memories go in a new folder either way."""
    started = dt.datetime.now()
    base, k = Path(memories) / f"{suite}-{slug(contender.name)}-{started:%Y%m%d-%H%M%S}", 1
    root = base.with_name(base.name + ".nosync")
    while root.exists() or (resume is not None and str(root) in _folders(resume)):  # never an earlier run's memory
        k += 1
        root = base.with_name(f"{base.name}-{k}.nosync")
    keys = KEYS.get(suite, ())
    if resume is None:
        path = record_path(suite, contender.name, started, records)
        record: dict[str, Any] = {"kind": "suite", "task": suite, "contender": contender.describe(),
                                  "thinking": getattr(contender, "thinking", THINKING), "settings": settings or {},
                                  "max_tokens": {**MAX_TOKENS, "other": OTHER_TOKENS, "by_suite": LIMITS},
                                  "folder": str(root), "started": started.isoformat(timespec="seconds"),
                                  "environment": environment(), "groups": []}
    else:
        record, path = resume, Path(resume["path"])
        kept = [g for g in record.get("groups") or [] if finished(g)]
        record.setdefault("resumes", []).append({
            "at": started.isoformat(timespec="seconds"), "kept_groups": len(kept), "folder": str(root),
            "spent_usd_before": (record.get("contender") or {}).get("spent_usd"),
            "environment": environment()})
        record["groups"] = kept
        record["contender"] = contender.describe()
        record.pop("stopped", None)
    record["planned_groups"] = len(groups)
    record["complete"] = False
    done = {g["id"] for g in record["groups"]}
    everything: list[dict] = [a for g in record["groups"] for a in g.get("answers") or []]
    in_row = 0

    def save_now() -> None:
        record["summary"] = breakdown(everything, keys, suite)
        record["failed_groups"] = sum(g.get("outcome") == "error" for g in record["groups"])
        spent = (record.get("contender") or {}).get("spent_usd")
        if spent is not None and record.get("resumes"):
            record["spent_usd_all"] = round(sum(r.get("spent_usd_before") or 0.0 for r in record["resumes"]) + spent, 6)
        record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        if save:
            record["path"] = str(write_record(record, path))

    try:
        for g in groups:
            if g.id in done:
                continue
            folder = root / slug(g.id)
            entry: dict[str, Any] = {"id": g.id, "meta": g.meta, "folder": str(folder), "outcome": "ok",
                                     "told": 0}
            stage = "open"
            read0 = _safe(contender.reading_s, 0.0)
            t = time.perf_counter()
            try:
                contender.open(folder)
                if callable(getattr(contender, "expect", None)):
                    contender.expect(len(g.asks))
                stage = "tell"
                for text in g.tells:
                    contender.tell(text, 0)
                    entry["told"] += 1
            except StopRun as e:
                record["stopped"] = str(e)
                entry.update(outcome="stopped", stage=stage)
            except Exception as e:  # noqa: BLE001: one context that fails is recorded, and the run goes on
                entry.update(outcome="error", stage=stage, error=f"{type(e).__name__}: {e}"[:400])
            tell_s = time.perf_counter() - t
            answers: list[dict] = []
            if entry["outcome"] == "ok":
                in_row = 0
                try:
                    for a in g.asks:
                        answers.append(ask_one(contender, a, {**g.meta, "group": g.id}))
                except StopRun as e:
                    record["stopped"] = str(e)
                    entry["outcome"] = "stopped"
            elif entry["outcome"] == "error":
                in_row += 1
                if in_row >= MAX_FAILED:
                    record["stopped"] = (f"{in_row} contexts in a row failed to open or be told; the last: "
                                         f"{entry['error']}")
            everything += answers
            entry.update(tell_s=round(tell_s, 3), read_s=round(max(_safe(contender.reading_s, 0.0) - read0, 0.0), 3),
                         status=_safe(contender.status), answers=answers)
            record["groups"].append(entry)
            record["contender"] = _safe(contender.describe)
            save_now()
            s = summarize(answers)["all"] if answers else {"right": 0, "graded": 0, "questions": 0, "ttft_s": {}}
            head = f"right {s['right']}/{s['graded']} graded of {s['questions']}"
            if entry["outcome"] != "ok":
                head += f", {entry['outcome']}"
                if "error" in entry:
                    head += f" at {entry['stage']}: {entry['error']}"
            progress(f"{contender.name} {suite} {g.id}: {head}, told {entry['told']} in {tell_s:.1f} s, first word "
                     f"p50 {(s.get('ttft_s') or {}).get('p50')} s")
            if "stopped" in record:
                progress(f"stopped: {record['stopped']}")
                break
        else:
            record["complete"] = all(finished(g) for g in record["groups"]) and \
                {g["id"] for g in record["groups"]} >= {g.id for g in groups}
    finally:
        try:
            contender.close()
        except Exception as e:  # noqa: BLE001: the record is still written
            record["close_error"] = f"{type(e).__name__}: {e}"[:400]
        record["contender"] = _safe(contender.describe)
        save_now()
    return record


def _split(values: Sequence[str] | None) -> list[str]:
    return [x.strip() for v in (values or []) for x in v.split(",") if x.strip()]


def plan(suite: str, a: argparse.Namespace, contender: str) -> tuple[list[Group], dict]:
    """The groups a command line asks for, and the settings the record keeps."""
    n = a.n if a.n is not None else DEFAULT_N[suite]
    settings: dict[str, Any] = {"n": n, "seed": a.seed}
    if suite == "babilong":
        from engram.bench.suites import babilong

        lengths = _split(a.lengths) or [*LENGTHS, *(BIG_LENGTHS if is_claude(contender) else ())]
        bad = set(lengths) - set(babilong.LENGTHS)
        if bad:
            raise ValueError(f"no BABILong length {', '.join(sorted(bad))}; there are {', '.join(babilong.LENGTHS)}")
        tasks = _split(a.tasks) or list(babilong.TASKS)
        settings.update(lengths=lengths, tasks=tasks, tell_tokens=TELL_TOKENS)
        return plan_babilong(n, a.seed, lengths, tasks), settings
    if suite == "memoryagentbench":
        settings["splits"] = ["Conflict_Resolution"]
        return plan_memoryagentbench(n, a.seed), settings
    if suite == "math500":
        levels = [int(x) for x in _split(a.levels)] or list(LEVELS)
        settings["levels"] = levels
        return plan_math500(n, a.seed, levels), settings
    if suite == "aime":
        years = [int(x) for x in _split(a.years)] or [2025, 2026]
        settings["years"] = years
        return plan_aime(n, a.seed, years), settings
    modes = _split(a.memory) or ["on", "off"]
    if set(modes) - {"on", "off"}:
        raise ValueError("--memory is on, off, or both")
    settings.update(modes=modes, noise_tokens=a.noise_tokens, haul=str(a.haul))
    return plan_harp(n, a.seed, modes, noise_tokens=a.noise_tokens, haul=a.haul), settings


def resume_problem(record: dict, suite: str, name: str, settings: dict) -> str | None:
    """Why ``record`` cannot be resumed as this run (another suite, contender or plan), or None."""
    if record.get("kind") != "suite" or record.get("task") != suite:
        return f"it is not a {suite} suite record"
    had = (record.get("contender") or {}).get("name")
    if had != contender_name(name):
        return f"it is {had}'s, not {contender_name(name)}'s"
    old = {k: v for k, v in (record.get("settings") or {}).items() if k not in SETTINGS_FREE}
    new = {k: v for k, v in json.loads(json.dumps(settings, default=str)).items() if k not in SETTINGS_FREE}
    if old != new:
        return f"its plan was {old}, not {new}"
    return None


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m engram.bench.suite_run",
                                 description="A Hugging Face suite for one contender: Ollama or Claude.")
    ap.add_argument("suite", help=", ".join(SUITES))
    ap.add_argument("--contender", required=True,
                    help="ollama:<model>, ollama-bare:<model> or claude-<model> (the local contenders are not run on "
                         "the suites yet)")
    ap.add_argument("--n", type=int, help="babilong: stories per task; memoryagentbench: questions per context; "
                                          "math500: problems; aime: problems a year (default all); harp: pairs")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lengths", nargs="+", help="babilong: e.g. 4k 16k (default 4k to 128k, and 512k and 1M for "
                                                 "Claude)")
    ap.add_argument("--tasks", nargs="+", help="babilong: e.g. qa1 qa2")
    ap.add_argument("--levels", nargs="+", help="math500: default 3 4 5")
    ap.add_argument("--years", nargs="+", help="aime: default 2025 2026")
    ap.add_argument("--memory", nargs="+", help="harp: on, off, or both (the default)")
    ap.add_argument("--noise-tokens", type=int, default=NOISE_TOKENS, help="harp: Long Haul noise told after A")
    ap.add_argument("--haul", type=Path, default=HAUL, help="harp: the built Long Haul the noise comes from")
    ap.add_argument("--max-usd", type=float, default=10.0, help="Claude: this invocation never spends more")
    ap.add_argument("--think-room", type=int, default=THINK_ROOM,
                    help="Claude: tokens to think in, on top of the reply limit")
    ap.add_argument("--estimate", action="store_true", help="print the plan (and Claude's cost estimate), then stop")
    ap.add_argument("--resume", type=Path, help="an earlier record of this run: its finished contexts are kept and "
                                                "skipped, the rest are run and added to it")
    ap.add_argument("--port", type=int, default=PROXY_PORT, help="ollama: the pairing proxy's port")
    ap.add_argument("--records", type=Path, default=RECORDS)
    ap.add_argument("--memories", type=Path, default=MEMORIES)
    return ap


def _line(name: str, s: dict) -> str:
    return (f"{name}: right {s.get('right')}/{s.get('graded')} graded of {s.get('questions')} (errors "
            f"{s.get('errors')}, truncated {s.get('truncated')})")


def main(argv: Sequence[str] | None = None) -> int:
    from engram.bench.suites import module

    a = parser().parse_args(argv)
    try:
        suite = module(a.suite).NAME
    except KeyError as e:
        print(e.args[0], file=sys.stderr)
        return 2
    if suite not in SUITES:
        print(f"suite_run runs {', '.join(SUITES)}; not {suite}", file=sys.stderr)
        return 2
    if not (is_claude(a.contender) or is_ollama(a.contender)):
        print(LOCAL_REFUSED if a.contender.startswith(LOCAL_KINDS) else
              f"no contender {a.contender!r}: use ollama:<model>, ollama-bare:<model> or claude-<model>",
              file=sys.stderr)
        return 2
    try:
        groups, settings = plan(suite, a, a.contender)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    resume, todo = None, groups
    if a.resume:
        try:
            resume = json.loads(Path(a.resume).read_text())
        except (OSError, ValueError) as e:
            print(f"cannot read {a.resume}: {e}", file=sys.stderr)
            return 2
        why = resume_problem(resume, suite, a.contender, settings)
        if why:
            print(f"cannot resume {a.resume}: {why}", file=sys.stderr)
            return 2
        resume["path"] = str(a.resume)
        done = {g["id"] for g in resume.get("groups") or [] if finished(g)}
        todo = [g for g in groups if g.id not in done]
    left = f"; resuming {a.resume}: {len(groups) - len(todo)} done, {len(todo)} to run" if resume is not None else ""
    print(f"{suite}: {len(groups)} contexts, {sum(len(g.asks) for g in groups)} questions, for {a.contender}{left}")
    if is_claude(a.contender):
        model = a.contender.removeprefix("claude:")
        est = estimate(todo, model, a.think_room)
        print(f"estimate for {model}: ${est['expected_usd']:.4f} expected, ${est['worst_usd']:.4f} if every reply used "
              f"all its room ({est['calls']} calls, about {est['prompt_tokens']:,} prompt tokens); the run stops "
              f"before it could pass ${a.max_usd:.2f}")
        settings.update(estimate=est, max_usd=a.max_usd, think_room=a.think_room)
        if not a.estimate and est["expected_usd"] > a.max_usd:
            print(f"not started: ${est['expected_usd']:.2f} expected is over --max-usd {a.max_usd:.2f}",
                  file=sys.stderr)
            return 2
    if a.estimate:
        return 0
    contender = make_contender(a.contender, max_usd=a.max_usd, think_room=a.think_room, port=a.port, task=suite)
    record = run(suite, contender, groups, settings=settings, records=a.records, memories=a.memories, resume=resume)
    s = record.get("summary", {})
    spent = record["contender"].get("spent_usd")
    print(_line("all" + (f" ({', '.join(s.get('lengths') or [])})" if suite == "babilong" else ""), s.get("all", {}))
          + (f", ${spent:.4f} spent" if spent is not None else ""))
    if suite == "babilong":
        print(_line(f"shared ({LENGTHS[0]}-{LENGTHS[-1]}, every contender's)", s.get("shared", {})))
        for length, ls in (s.get("by_length") or {}).items():
            print(_line(f"  {length}", ls))
    if not record.get("complete"):
        why = record.get("stopped") or (f"{record.get('failed_groups')} contexts failed, "
                                        f"{(s.get('all') or {}).get('errors')} questions failed")
        print(f"not complete ({why}): --resume {record.get('path')} runs the rest")
    print(record.get("path"))
    return 0


__all__ = ["Ask", "ClaudeContender", "Group", "LOCAL_REFUSED", "StopRun", "breakdown", "estimate", "finished",
           "make_contender", "plan_aime", "plan_babilong", "plan_harp", "plan_math500", "plan_memoryagentbench",
           "resume_problem", "run", "truncated"]


if __name__ == "__main__":
    from engram.app.measuring import measuring

    with measuring("suite_run"):  # the app pauses its views and loads nothing while this measures
        raise SystemExit(main())
