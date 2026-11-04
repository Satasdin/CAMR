"""Memory reach: how far a memory goes. A session's own memory, a project's, an agent's, or one global memory
shared by everything. Each reach is its own folder under one root (``~/.camr`` by default), holding its rooms and
its vault:

    ~/.camr/global/
    ~/.camr/project/<name>/
    ~/.camr/agent/<name>/
    ~/.camr/session/<id>/

A session reads several reaches at once (for example its own and the global one). A question picks the best room
over all of them: the room of the closest moment in any of them, with that memory's closest moments as words. New
moments go to one reach, the session's own unless told otherwise. Memory has a switch: off, the session is the plain
model with no memory at all, and nothing is read or kept.

A reach folder is open once per process: every session reading it shares one Memory, which closes when the last of
them closes. Another process cannot open it meanwhile (a lock on ``<reach>/.lock``), since two writers of one room
file would cut each other's notes.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from camr_engine.core import CORE_TOKENS, Core
from camr_engine.memory import Memory, Recall
from camr_engine.metrics import Meter, measure
from camr_engine.swap import RAM_BYTES, Pool, Tiers

KINDS = ("session", "project", "agent", "global")
ROOT = Path.home() / ".camr"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class Reach:
    kind: str
    name: str = ""

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"reach is one of {KINDS}, not {self.kind!r}")
        if self.kind == "global":
            if self.name:
                raise ValueError("there is one global reach; it has no name")
        elif not _NAME.match(self.name or ""):
            raise ValueError(f"a {self.kind} reach needs a plain name (letters, digits, . _ -), not {self.name!r}")

    @property
    def label(self) -> str:
        """``global``, or kind and name, as in ``project:tally``."""
        return self.kind if self.kind == "global" else f"{self.kind}:{self.name}"

    def path(self, root: Path = ROOT) -> Path:
        return Path(root) / self.kind if self.kind == "global" else Path(root) / self.kind / self.name

    @classmethod
    def parse(cls, text: str) -> Reach:
        """``global``, ``session:<id>``, ``project:<name>`` or ``agent:<name>``."""
        kind, _, name = text.partition(":")
        return cls(kind.strip(), name.strip())

    def __str__(self) -> str:
        return self.label


def new_session() -> str:
    """A fresh session id: when it started, and a few random letters so two sessions never share one."""
    return f"{dt.datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


class ReachBusy(RuntimeError):
    """The reach folder is open in another process."""


@dataclass
class _Open:
    memory: Memory
    users: int
    lock: int  # the open lock file, held while any session here uses the reach


_OPEN: dict[Path, _Open] = {}  # reach folder -> its one Memory in this process
_GUARD = threading.Lock()


def _same(a, b, attr: str) -> bool:
    """The same model: the same object, or two loads of one model."""
    return a is b or (getattr(a, attr, None) is not None and getattr(a, attr, None) == getattr(b, attr, None))


def _lock(folder: Path, label: str) -> int:
    fd = os.open(folder / ".lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise ReachBusy(f"the {label} memory at {folder} is open in another process; close it there first") from None
    return fd


def opened(path: Path) -> Memory | None:
    """The Memory open in this process for a reach folder, if any."""
    got = _OPEN.get(Path(path).resolve())
    return got.memory if got is not None else None


def _acquire(path: Path, label: str, reader, embedder, make: Callable[[], Memory]) -> tuple[Path, Memory]:
    """The one Memory for a reach folder in this process: made (and locked) by the first session to read it, shared
    with every later one."""
    folder = Path(path)
    folder.mkdir(parents=True, exist_ok=True)
    key = folder.resolve()
    with _GUARD:
        got = _OPEN.get(key)
        if got is not None:
            m = got.memory
            if not (_same(m.reader, reader, "repo") and _same(m.embedder, embedder, "name")):
                raise ValueError(f"the {label} memory is already open here with another reader or embedder")
            got.users += 1
            return key, m
        fd = _lock(key, label)
        try:
            m = make()
        except BaseException:
            os.close(fd)
            raise
        _OPEN[key] = _Open(m, 1, fd)
        return key, m


def _release(key: Path) -> None:
    """One session lets go of a reach: saved now, and closed (its lock let go) when no session uses it."""
    with _GUARD:
        got = _OPEN.get(key)
        if got is None:
            return
        got.users -= 1
        try:
            got.memory.save()
            if got.users <= 0:
                got.memory.close()
        finally:
            if got.users <= 0:
                del _OPEN[key]
                os.close(got.lock)


class Session:
    """One conversation's memory over the reaches it reads.

    ``reads`` names the reaches, in order of preference when two are equally close: ``session``, ``project``,
    ``agent``, ``global``, or a Reach. ``writes`` is where new moments go (read too). ``project`` and ``agent`` name
    those reaches; ``name`` is the session's id (a new one by default). ``vault``, ``tiers`` (a dict of Tiers
    options: each reach gets its own disk budget, and all share one RAM budget) and every other Memory setting apply
    to each reach this session opens; a reach another session here already has open is shared as it is, with the
    settings it was opened with. One core is built from the core notes of every reach read, and goes on every desk.
    Close the session when done: that saves every reach and lets go of them."""

    def __init__(self, reader, embedder, *, root: Path = ROOT, name: str | None = None, project: str | None = None,
                 agent: str | None = None, reads: Iterable[str | Reach] = ("session", "global"),
                 writes: str | Reach = "session", on: bool = True, vault: bool = True, core: bool = False,
                 core_tokens: int = CORE_TOKENS, tiers: dict | None = None, metrics: bool = False,
                 plain_system: str | None = None, **settings):
        self.reader, self.embedder, self.root, self.on = reader, embedder, Path(root), on
        self.name, self.project, self.agent = name or new_session(), project, agent
        self.plain_system = plain_system
        self.home = self._reach(writes)
        self.reaches = list(dict.fromkeys([self._reach(r) for r in reads]))
        if self.home not in self.reaches:
            self.reaches.insert(0, self.home)
        self.memories: dict[Reach, Memory] = {}
        self._held: list[Path] = []
        self.pool: Pool | None = None
        if tiers is not None:  # one RAM budget for the core and every reach's hot rooms
            tiers = dict(tiers)
            self.pool = Pool(tiers.pop("ram_bytes", RAM_BYTES))
        # the header is read once and shared by every reach (with a reach already open here, its header is used)
        open_ = [opened(r.path(self.root)) for r in self.reaches]
        self.notebook = next((m.notebook for m in open_ if m is not None), None)
        try:
            for r in self.reaches:
                def make(r=r):
                    return Memory(reader, embedder, r.path(self.root), notebook=self.notebook, vault=vault,
                                  reach=r.label, tiers=Tiers(**tiers, pool=self.pool) if tiers is not None else None,
                                  metrics=metrics, **settings)
                key, m = _acquire(r.path(self.root), r.label, reader, embedder, make)
                self._held.append(key)
                if self.notebook is None:
                    self.notebook = m.notebook
                self.memories[r] = m
        except BaseException:
            self.close()
            raise
        self.core: Core | None = None
        if core:
            vaults = [m.vault for m in self.memories.values() if m.vault is not None]
            if not vaults:
                self.close()
                raise ValueError("the core is built from vault notes: keep vault=True")
            self.core = Core(self.notebook, self.memories[self.home].ids, vaults, budget=core_tokens)
        self.meter = Meter()  # every answer this session gave, memory on or off
        self.last: Recall | None = None

    def _reach(self, r: str | Reach) -> Reach:
        if isinstance(r, Reach):
            return r
        if ":" in r:
            return Reach.parse(r)
        names = {"session": self.name, "project": self.project, "agent": self.agent, "global": ""}
        if r not in names:
            raise ValueError(f"reach is one of {KINDS}, not {r!r}")
        if r != "global" and not names[r]:
            raise ValueError(f"reading the {r} reach needs its name: pass {r}=...")
        return Reach(r, names[r])

    def switch(self, on: bool) -> None:
        """Memory on or off. Off: the plain model, nothing read, nothing kept."""
        self.on = on

    def memory(self, reach: str | Reach | None = None) -> Memory:
        return self.memories[self.home if reach is None else self._reach(reach)]

    def remember(self, text: str, day: int, *, to: str | Reach | None = None, **kw):
        """Keep a moment in the session's own reach, or ``to`` another it reads. Nothing is kept while off."""
        if not self.on:
            return None
        reach = self.home if to is None else self._reach(to)
        if reach not in self.memories:
            raise ValueError(f"this session does not read {reach.label}")
        m = self.memories[reach]
        got = m.remember(text, day, **kw)
        if reach.kind != "session":  # a shared memory is saved at once, so its index is never behind its files
            m.save()
        return got

    def choose(self, question: str) -> tuple[Memory, Recall]:
        """The best room over every reach: the one holding the moment closest to the question. Earlier reaches win
        ties. The question is embedded once."""
        t = time.perf_counter()
        vec = self.embedder.encode_one(question, is_query=True)
        best: tuple[Memory, Recall] | None = None
        for m in self.memories.values():
            rec = m.choose(question, vec=vec)
            if rec.score is not None and (best is None or rec.score > best[1].score):
                best = (m, rec)
        if best is None:
            home = self.memories[self.home]
            best = (home, Recall(None, [], 0, 0, reach=home.reach))
        best[1].seconds["choose"] = time.perf_counter() - t
        return best

    def recall(self, question: str) -> Recall:
        m, rec = self.choose(question)
        return m.recall(question, chosen=rec, core=self.core)

    def answer(self, question: str, today: dt.date, **kw):
        """Answer from the best room over every reach; with memory off, the plain model alone. The wait is counted
        from the question, choosing included, and the record counts every reach's history and disk."""
        if not self.on:
            return self.plain(question, today, **kw)
        t = time.perf_counter()
        m, rec = self.choose(question)
        reply = m.answer(question, today, chosen=rec, started=t, core=self.core, record=True,
                         among=list(self.memories.values()), **kw)
        self.last = rec
        self.meter.add(reply.metrics)
        return reply

    def plain(self, question: str, today: dt.date, *, then: str = "", tools: list | None = None,
              max_tokens: int | None = None, **_):
        """The model with no memory: the same prompt with no notes (or ``plain_system`` when given), read whole."""
        t = time.perf_counter()
        if self.plain_system is not None:
            ids = self.reader.chat_ids(self.plain_system, question, tools)
        else:
            head, rest = self.memories[self.home].prompt(today, question, then, tools)
            ids = head + rest
        reply = self.reader.generate(ids, max_tokens=max_tokens)
        done = time.perf_counter() - t
        self.last = None
        reply.metrics = self.meter.add(measure(question, reply, Recall(None, [], 0, 0), total_s=done,
                                               first_s=reply.ttft_s, new_tokens=len(ids), history_tokens=0,
                                               disk_bytes=0, reach=None))
        return reply

    def state(self) -> dict:
        """Each reach's memory, and the core, for a person to look at."""
        out = {"session": self.name, "on": self.on, "writes": self.home.label,
               "reaches": {r.label: m.state() for r, m in self.memories.items()}}
        if self.core is not None:
            out["core"] = {"tokens": self.core.tokens, "notes": list(self.core.members),
                           "left_out": list(self.core.left_out)}
        return out

    def save(self) -> None:
        for m in self.memories.values():
            m.save()

    def close(self) -> None:
        """Save every reach and let go of them (each closes when no other session here reads it)."""
        held, self._held = self._held, []
        for key in held:
            _release(key)

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
