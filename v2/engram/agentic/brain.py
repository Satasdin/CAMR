"""The model the agent's loop talks to. With memory on, it is the engine: a reach session (engram.reach) whose
best room for the task is laid on the desk before every step, and the step's answer event (what was picked up, how
hard each written word looked at it) is kept in that reach's log. With memory off, it is the plain local model.

Both take the same prompt: the persona and the rules as instructions, and the task with every step so far as the
user's message. The engine's header stays the memory's own (it is read once and shared by every reach), so the
instructions follow the notes, as for errands (``engram.agent``).

A step's memory, as the loop keeps it:
- ``reach``, ``room``, ``tier`` (ram, ssd or vault), ``read_bytes``, ``seconds`` (choose, core, fetch, wake, desk),
  ``gbps``;
- ``nodes`` (moments on the desk), ``used`` (those that drew at least 0.10 of its attention), ``share``,
  ``closest`` (moments re-read as words), ``fixes`` (nodes that are saved fixes, read as vault notes);
- ``lean``: for each written word, the node it looked at hardest and how hard, which the memory gutter joins to the
  lines of code the model wrote;
- ``metrics``: the answer's record (first word, total, prefill and decode speed, context against history).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

FIX = "Your fix"  # the start of every saved-fix moment (after its date)
_DATED = re.compile(r"^\[\d{4}-\d{2}-\d{2}\]\s*")


def is_fix(text: str) -> bool:
    """A saved-fix moment: its words start with FIX once the date ``keep`` puts in front is left aside."""
    return _DATED.sub("", text or "", count=1).startswith(FIX)


@dataclass
class Prompt:
    system: str  # the persona, the rules, the workspace and the skills
    user: str  # the task and every step so far
    tools: list[dict]
    ask: str  # what memory is chosen by: the task itself, not the whole transcript
    max_tokens: int = 768
    tags: dict = field(default_factory=dict)  # kept with the step's event: run, step, agent


@dataclass
class Thought:
    text: str  # the whole reply, as written (pieces joined)
    pieces: list[str]
    first_s: float
    total_s: float
    prompt_tokens: int
    gen_tokens: int
    decode_tps: float | None
    memory: dict | None = None


class Brain(Protocol):
    label: str
    memory_on: bool

    def think(self, prompt: Prompt) -> Thought: ...

    def keep(self, text: str, to: str | None = None) -> dict | None: ...

    def moment(self, reach: str, mid: int) -> dict | None: ...

    def reaches(self) -> list[dict]: ...

    def close(self) -> None: ...


def last_line(path: Path, limit: int = 8 << 20) -> dict | None:
    """The last JSON line of a log, read from its end."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            step, buf = 65536, b""
            pos = size
            while pos > 0 and size - pos < limit:
                take = min(step, pos)
                pos -= take
                f.seek(pos)
                buf = f.read(take) + buf
                lines = buf.rstrip(b"\n").split(b"\n")
                if len(lines) > 1 or pos == 0:
                    return json.loads(lines[-1]) if lines[-1] else None
    except (OSError, ValueError):
        return None
    return None


def lean(looks: list[list[float]], nodes: list[int]) -> list[list]:
    """For each written word: [the node it looked at hardest, how hard], or [None, 0]."""
    out = []
    for row in looks or []:
        if not row or not nodes:
            out.append([None, 0.0])
            continue
        j = max(range(len(row)), key=lambda k: row[k])
        out.append([nodes[j], round(float(row[j]), 4)])
    return out


class PlainBrain:
    """The local model with no memory: the persona as the system message, the task and steps as the user's."""

    memory_on = False

    def __init__(self, reader, label: str | None = None):
        self.reader = reader
        self.label = label or getattr(reader, "repo", None) or "model"

    def think(self, p: Prompt) -> Thought:
        t = time.perf_counter()
        ids = self.reader.chat_ids(p.system, p.user, p.tools)
        reply = self.reader.generate(ids, max_tokens=p.max_tokens)
        return Thought("".join(reply.pieces) or reply.text, list(reply.pieces), reply.ttft_s,
                       time.perf_counter() - t, reply.prompt_tokens, reply.gen_tokens, reply.gen_tps or None)

    def keep(self, text: str, to: str | None = None) -> dict | None:
        return None

    def moment(self, reach: str, mid: int) -> dict | None:
        return None

    def reaches(self) -> list[dict]:
        return []

    def close(self) -> None:
        pass


ENGINE_RULES = ("This request is a task in the user's project, not a question about the notes: the one-sentence "
                "rule above does not apply. Use the notes above when they help: names, rules, decisions and fixes "
                "from earlier work.")


class EngineBrain:
    """The engine as the agent's memory: a reach session (made by the caller, closed here)."""

    memory_on = True

    def __init__(self, session, *, label: str | None = None, today: Callable[[], dt.date] = dt.date.today,
                 day: Callable[[dt.date], int] | None = None):
        self.session = session
        self.label = label or getattr(session.reader, "repo", None) or "model"
        self.today, self.day = today, day or (lambda d: (d - dt.date(2026, 1, 5)).days)

    def think(self, p: Prompt) -> Thought:
        s = self.session
        t = time.perf_counter()
        m, rec = s.choose(p.ask)
        reply = m.answer(p.user, self.today(), then=f"{ENGINE_RULES}\n\n{p.system}", tools=p.tools,
                         max_tokens=p.max_tokens, kind="agent", chosen=rec, started=t, core=s.core, record=True,
                         among=list(s.memories.values()), **p.tags)
        s.last = rec
        if getattr(reply, "metrics", None) is not None:
            s.meter.add(reply.metrics)
        return Thought("".join(reply.pieces) or reply.text, list(reply.pieces), reply.ttft_s,
                       time.perf_counter() - t, reply.prompt_tokens, reply.gen_tokens, reply.gen_tps or None,
                       self._memory(m, rec, reply))

    def _memory(self, m, rec, reply) -> dict:
        event = last_line(m.log.path) if m.log is not None else None
        if event is not None and event.get("type") != "agent":
            event = None
        nodes = list(event.get("nodes") or []) if event else []
        out = {"reach": rec.reach, "room": rec.room, "tier": rec.tier, "read_bytes": rec.read_bytes,
               "asleep": rec.asleep, "seconds": {k: round(v, 4) for k, v in rec.seconds.items()},
               "gbps": rec.gbps, "closest": list(rec.closest), "nodes": nodes,
               "used": list(event.get("used") or []) if event else [],
               "share": list(event.get("share") or []) if event else [],
               "lean": lean(event.get("looks"), nodes) if event else [],
               "fixes": [n for n in nodes if is_fix(self._text(m, n))], "logged": event is not None,
               "event_at": event.get("at") if event else None}
        rec_metrics = getattr(reply, "metrics", None)
        if rec_metrics is not None:
            d = rec_metrics.to_dict() if hasattr(rec_metrics, "to_dict") else dict(rec_metrics)
            out["metrics"] = {k: d.get(k) for k in ("first_word_s", "total_s", "prefill_tps", "decode_tps",
                                                     "retrieval_ms", "read_share", "context_tokens",
                                                     "history_tokens", "peak_ram_bytes", "disk_bytes")}
        return out

    @staticmethod
    def _text(m, mid: int) -> str:
        try:
            return m.rooms.moments[mid].text
        except (IndexError, AttributeError):
            return ""

    def keep(self, text: str, to: str | None = None) -> dict | None:
        """Remember a moment, dated, in the reach this session writes to, or ``to`` another it reads (such as
        ``project``)."""
        s = self.session
        today = self.today()
        got = s.remember(f"[{today.isoformat()}] {text}", self.day(today), to=to)
        if got is None:
            return None
        m = s.memory(to)
        m.save()
        return {"reach": m.reach, "moment": got.mid, "room": got.room}

    def moment(self, reach: str, mid: int) -> dict | None:
        for m in self.session.memories.values():
            if m.reach == reach and 0 <= mid < len(m.rooms.moments):
                x = m.rooms.moments[mid]
                return {"reach": reach, "moment": mid, "room": x.room, "day": x.day, "text": x.text}
        return None

    def reaches(self) -> list[dict]:
        """Each reach this session reads: its rooms (tokens, bytes, hot in RAM, asleep) for the wells and the rack."""
        out = []
        for r, m in self.session.memories.items():
            tiers = m.tiers
            hot = set(tiers.hot) if tiers is not None else set()
            asleep = set(tiers.sleeping) if tiers is not None else set()
            tb = m.rooms.token_bytes
            out.append({"reach": r.label, "kind": r.kind, "writes": r == self.session.home,
                        "moments": len(m.rooms.moments), "history_tokens": m.history_tokens(),
                        "rooms": [{"id": x.rid, "tokens": x.tokens, "bytes": x.tokens * tb, "hot": x.rid in hot,
                                   "asleep": x.rid in asleep} for x in m.rooms.rooms]})
        return out

    def close(self) -> None:
        self.session.close()
