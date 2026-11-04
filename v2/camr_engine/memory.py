"""CAMR's memory, step 1: every moment becomes notes in a room on the SSD; a question opens the one room it is
about and re-reads its few closest moments as words.

Remember: a moment is embedded, placed in the room holding its closest moment, and read by the model with that
room's earlier moments in view; its notes are appended to the room's file. Recall: the question is embedded; the
room holding its closest moment is read from the SSD in one burst and laid on the desk behind the header, already
read; the few moments closest to the question are then read as words, in date order, just before the question.

One room, not several: rooms written apart and laid side by side lose the thread, and a 1.7B model knew fewer facts
from three rooms' notes than from one room's notes plus its closest moments as words (DECISIONS.md, E-16).

The engine's other layers are switched on by options, each off by default, so that without them everything here
computes exactly what it did in step 1:
- ``vault``: the archive, one Markdown note per moment, with doors between notes (camr_engine.vault);
- ``core``: the subconscious, a small block of core notes on every desk before the room (camr_engine.core);
- ``tiers``: RAM and disk budgets, hot rooms in RAM and asleep rooms read as words (camr_engine.swap);
- ``metrics``: one record per answer of what it cost (camr_engine.metrics);
- ``notebook``: a header already read, shared by several memories (camr_engine.reach).
"""

from __future__ import annotations

import datetime as dt
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

from camr_engine.core import CORE_TOKENS, Core
from camr_engine.live import current
from camr_engine.events import EventLog, Looks, used
from camr_engine.metrics import Meter, folder_bytes, measure
from camr_engine.notes import Notebook
from camr_engine.rooms import Rooms
from camr_engine.swap import SSD, Tiers
from camr_engine.vault import INDEX, SHARE, Vault

INTRO = ("You are a personal assistant that remembers the user's own notes. Answer the user's question in one short "
         "sentence, using only the notes below. If the notes do not contain the answer, reply exactly: I don't know.")
_SLOT = "⁣NOTES⁣"  # where the room goes; never typed by a person

ROOM_TOKENS = 512  # at most 57 MB of notes on the 1.7B, inside the 256 MB allowance
JOIN = 0.80  # how close a moment must be to a room's closest moment to join it
CLOSEST = 4  # moments re-read as words after the room
ALLOWANCE_BYTES = 256 * 2**20
_OWN = object()  # "this memory's own core", as against a core (or None) a session passes in


def today_text(d: dt.date) -> str:
    return f"{d:%A} {d.day} {d:%B} {d.year}"


@dataclass
class Recall:
    room: int | None  # the room laid on the desk
    closest: list[int]  # moments re-read as words, in date order
    tokens: int  # the room's tokens
    bytes: int
    desk: list | None = None  # the cache to answer from (None when the room was only chosen)
    seconds: dict[str, float] = field(default_factory=dict)
    score: float | None = None  # how close the closest moment is to the question
    tier: str | None = None  # where the room's notes came from: "ram", "ssd", or "vault" (asleep)
    read_bytes: int = 0  # read from the SSD for this recall
    asleep: bool = False  # the room's notes were asleep, so its moments are read as words
    core: int = 0  # core tokens on the desk, between the header and the room
    reach: str | None = None  # whose memory the room is in

    @property
    def gbps(self) -> float | None:
        s = self.seconds.get("fetch", 0.0)
        return self.read_bytes / s / 1e9 if self.read_bytes and s > 0 else None

    @property
    def ms(self) -> dict[str, float]:
        """Retrieval time per step, in milliseconds."""
        return {k: round(v * 1000, 3) for k, v in self.seconds.items()}


class Memory:
    def __init__(self, reader, embedder, path: Path, *, room_tokens: int = ROOM_TOKENS, join: float = JOIN,
                 closest: int = CLOSEST, allowance: int = ALLOWANCE_BYTES, log: bool = True,
                 notebook: Notebook | None = None, vault: Vault | bool = False, reach: str | None = None,
                 core: Core | bool = False, core_tokens: int = CORE_TOKENS, tiers: Tiers | None = None,
                 metrics: Meter | bool = False):
        self.reader, self.embedder, self.closest, self.allowance = reader, embedder, closest, allowance
        self.path, self.reach = Path(path), reach
        self.log = EventLog(Path(path) / "events.jsonl") if log else None
        if notebook is None:
            head, _ = self.prompt(dt.date(2026, 1, 1), "?")
            notebook = Notebook(reader, head)
        self.notebook = notebook
        self.dtype = self.notebook.core[0][0].dtype
        if room_tokens * self.notebook.shape.token_bytes > allowance:
            raise ValueError("a full room must fit the allowance")
        self.rooms = Rooms(path, self.notebook.shape.token_bytes, room_tokens, join)
        self.vault: Vault | None = (Vault(self.path / "vault", reach=reach) if vault is True
                                    else vault if isinstance(vault, Vault) else None)
        if core is True and self.vault is None:
            raise ValueError("the core is built from a vault's notes: pass vault=True as well")
        self.core: Core | None = (Core(self.notebook, self.ids, [self.vault], budget=core_tokens) if core is True
                                  else core if isinstance(core, Core) else None)
        self.tiers = tiers
        if tiers is not None:
            tiers.bind(self.rooms, convert=self._array, join=self._join, rewrite=self._rewrite,
                       strength=self._strength, notify=self._slept)
        self.meter: Meter | None = (Meter(self.path / "metrics.jsonl") if metrics is True
                                    else metrics if isinstance(metrics, Meter) else None)

    def prompt(self, today: dt.date, question: str, then: str = "", tools: list | None = None
               ) -> tuple[list[int], list[int]]:
        """The header (same every time, kept in RAM as notes) and the part after the room, as token ids. ``then``
        (instructions for this kind of request) and ``tools`` come after the notes, so the header never changes."""
        system = f"{INTRO}\n\nNotes:\n{_SLOT}End of notes.\nToday is {today_text(today)}." + (f"\n\n{then}" if then else "")
        text = self.reader.tok.apply_chat_template([{"role": "system", "content": system},
                                                    {"role": "user", "content": question}], tools=tools,
                                                   add_generation_prompt=True, enable_thinking=False, tokenize=False)
        head, rest = text.split(_SLOT)
        return self.reader.tok.encode(head), self.reader.tok.encode(rest)

    def ids(self, text: str) -> list[int]:
        return self.reader.tok.encode(text + "\n")

    def _array(self, buf):
        import mlx.core as mx

        s = self.notebook.shape
        x = mx.array(np.frombuffer(buf, dtype=np.uint16)).view(self.dtype)
        return x.reshape(-1, s.layers, 2, s.kv_heads, s.head_dim)

    def remember(self, text: str, day: int, *, date: dt.date | None = None, tags: tuple[str, ...] | list[str] = (),
                 pinned: bool = False):
        """Keep a moment. ``date``, ``tags`` and ``pinned`` go on its vault note, when there is a vault."""
        import mlx.core as mx

        ids = self.ids(text)
        vec = self.embedder.encode_one(text)
        rid = self.rooms.place(vec, len(ids))
        if self.tiers is None:
            after = None if rid is None else self._array(self.rooms.fetch([rid])[rid])
        else:
            if rid is not None and self.tiers.is_asleep(rid) and not self.tiers.wake:
                rid = None  # an asleep room takes no new moments: this one starts a room of its own
            after = None if rid is None else self.tiers.load(rid).data  # wakes the room when waking is on
        notes = self.notebook.write(ids, after)
        m = self.rooms.add(text, day, vec, bytes(np.array(notes.view(mx.uint16))), rid)
        slept: list[int] = []
        try:
            note = self._note(m, date, tags, pinned) if self.vault is not None else None
        finally:  # the hot copy of the room always matches its file, even if the vault failed
            if self.tiers is not None:
                slept = self.tiers.wrote(m.room, notes, m.tokens * self.rooms.token_bytes)
        if self.log:
            more = ({"note": note.id} if note is not None else {}) | ({"slept": slept} if slept else {})
            self.log.write("remember", moment=m.mid, room=m.room, day=day, tokens=m.tokens, new_room=rid is None,
                           **more)
        return m

    def choose(self, question: str, *, vec: np.ndarray | None = None) -> Recall:
        """The room holding the moment closest to the question, and the closest moments overall. ``vec`` is the
        question already embedded (a session asking several memories embeds it once)."""
        t = time.perf_counter()
        if not self.rooms.moments:
            return Recall(None, [], 0, 0, seconds={"choose": time.perf_counter() - t}, reach=self.reach)
        q = self.embedder.encode_one(question, is_query=True) if vec is None else vec
        sims = self.rooms.vectors @ q
        order = np.argsort(-sims)
        room = self.rooms.rooms[self.rooms.moments[int(order[0])].room]
        closest = sorted(int(m) for m in order[:self.closest])
        return Recall(room.rid, closest, room.tokens, room.tokens * self.rooms.token_bytes,
                      seconds={"choose": time.perf_counter() - t}, score=float(sims[int(order[0])]), reach=self.reach)

    def recall(self, question: str, *, chosen: Recall | None = None, core: Core | None | object = _OWN) -> Recall:
        """Choose (unless ``chosen`` already did), read the room from the SSD in one burst, and lay it on the desk:
        the header, then the core when there is one, then the room. ``core`` is the core to lay (a session's, or
        None for none) instead of this memory's own."""
        rec = self.choose(question) if chosen is None else chosen
        core = self._core(rec, self.core if core is _OWN else core)
        t = time.perf_counter()
        if self.tiers is None:
            data = self.rooms.fetch([rec.room]) if rec.room is not None else {}
            rec.seconds["fetch"] = time.perf_counter() - t
            if data:
                rec.tier, rec.read_bytes = SSD, len(data[rec.room])
            t = time.perf_counter()
            rec.desk = self.notebook.desk(core + ([self._array(data[rec.room])] if data else []))
            rec.seconds["desk"] = time.perf_counter() - t
            return rec
        got = self.tiers.load(rec.room) if rec.room is not None else None
        rec.seconds["fetch"] = got.seconds if got is not None else 0.0
        if got is not None:
            rec.tier, rec.read_bytes, rec.asleep = got.tier, got.bytes, got.data is None
            if got.woke:
                rec.seconds["wake"] = got.wake_s
        t = time.perf_counter()
        rec.desk = self.notebook.desk(core + ([got.data] if got is not None and got.data is not None else []))
        rec.seconds["desk"] = time.perf_counter() - t + (got.convert_s if got is not None else 0.0)
        return rec

    def answer(self, question: str, today: dt.date, *, then: str = "", tools: list | None = None,
               max_tokens: int | None = None, kind: str = "answer", chosen: Recall | None = None,
               day: int | None = None, started: float | None = None, core: Core | None | object = _OWN,
               record: bool = False, among: Iterable[Memory] | None = None, **extra):
        """Answer from the desk, and log what was picked up and how hard each written word looked at it. ``chosen``
        is a room already chosen (by a session, across its reaches); ``day`` is today's day number for the vault
        (worked out from ``today`` when not given).

        For a session: ``started`` is when the question was asked (``time.perf_counter()``, before choosing), so
        the wait counts the choosing; ``core`` is the session's core; ``record`` builds the answer's metrics even
        without a meter; ``among`` is every memory the room was chosen among, whose history and disk the record
        counts."""
        t = time.perf_counter() if started is None else started
        head, rest = self.prompt(today, question, then, tools)
        rec = self.recall(question, chosen=chosen, core=core)
        live = current()
        if live is not None:  # the room on the desk, before any word is written
            live.add("room", reach=self.reach, room=rec.room, rooms=len(self.rooms.rooms), score=rec.score,
                     tier=rec.tier, tokens=rec.tokens, bytes=rec.bytes, read_bytes=rec.read_bytes,
                     asleep=rec.asleep, closest=len(rec.closest), core=rec.core, ms=rec.ms)
        lead = self.room_words(rec.room) if rec.asleep else []  # an asleep room is read as words
        ids = lead + self.words(rec.closest) + rest
        c = rec.core
        spans = [] if rec.room is None else [(m, c + self.rooms.moments[m].start, self.rooms.moments[m].tokens)
                                             for m in self.rooms.rooms[rec.room].members]
        at = c + rec.tokens
        for m in rec.closest:  # re-read as words, after the room
            n = len(self.ids(self.rooms.moments[m].text))
            spans.append((m, at, n))
            at += n
        desk = c + (0 if rec.asleep else rec.tokens)  # tokens on the desk already read, after the header
        before = time.perf_counter() - t
        if self.log:
            with Looks(self.reader, self.notebook.p, spans, self.notebook.p + desk + len(ids), rec.desk) as looks:
                reply = self.reader.generate(ids, cache=rec.desk, max_tokens=max_tokens)
        else:
            reply = self.reader.generate(ids, cache=rec.desk, max_tokens=max_tokens)
        done = time.perf_counter() - t
        first = reply.ttft_s
        reply.ttft_s += before
        reply.prompt_tokens += len(head) + desk
        use = None
        if self.log:
            per_word = looks.per_word(len(reply.pieces))
            share, use = used(per_word, looks.nodes)
            self.log.write(kind, question=question, room=rec.room, closest=rec.closest, nodes=looks.nodes,
                           share=share, used=use, words=reply.pieces,
                           looks=[[round(float(x), 4) for x in row] for row in per_word],
                           wait_s=round(reply.ttft_s, 4), seconds={k: round(v, 4) for k, v in rec.seconds.items()},
                           **{**self._more(rec), **extra})
        if self.vault is not None and use:
            self.use(use, today, day)
        if self.meter is not None or record:
            group = [self] if among is None else list(among)
            got = measure(question, reply, rec, total_s=done, first_s=first, new_tokens=len(ids),
                          history_tokens=sum(m.history_tokens() for m in group),
                          disk_bytes=sum(m.folder_bytes() for m in group), reach=self.reach)
            reply.metrics = self.meter.add(got) if self.meter is not None else got
        return reply

    def words(self, moments: list[int]) -> list[int]:
        return [i for m in moments for i in self.ids(self.rooms.moments[m].text)]

    def room_words(self, room: int | None) -> list[int]:
        """The room as words: what reading the text instead of the notes would cost."""
        return [] if room is None else self.words(self.rooms.rooms[room].members)

    def disk_bytes(self) -> int:
        return self.rooms.disk_bytes()

    # -- the engine's layers

    def use(self, moments: list[int], today: dt.date | None = None, day: int | None = None) -> None:
        """Moments used in one answer: their vault notes gain strength and the doors between them strengthen."""
        if self.vault is None:
            return
        d = day if day is not None else (self.vault.day_of(today) if today is not None else None)
        if d is not None:
            self.vault.use([self.vault.moment_id(m) for m in moments], d)

    def fade(self, today: int) -> tuple[int, list[int]]:
        """Bring the vault's strengths up to day ``today`` (first picking up every edit a person made to it), then
        hold the disk budget with them. Returns (notes changed, rooms put to sleep)."""
        if self.vault is not None:
            self.vault.rescan(full=True)
        changed = self.vault.fade(today) if self.vault is not None else 0
        slept = self.tiers.enforce() if self.tiers is not None else []
        return changed, slept

    def history_tokens(self) -> int:
        """Every token this memory holds, awake or asleep."""
        return sum(r.tokens for r in self.rooms.rooms)

    def folder_bytes(self) -> int:
        """Everything this memory keeps on disk: room files, index, logs, and the vault."""
        total = 0
        with os.scandir(self.path) as it:
            for e in it:
                if e.is_file(follow_symlinks=False):
                    total += e.stat(follow_symlinks=False).st_size
                elif e.is_dir(follow_symlinks=False):
                    if self.vault is not None and Path(e.path) == self.vault.path:
                        index = self.vault.path / INDEX
                        total += self.vault.disk_bytes() + (index.stat().st_size if index.exists() else 0)
                    else:
                        total += folder_bytes(Path(e.path))
        if self.vault is not None and self.vault.path.parent != self.path:
            total += self.vault.disk_bytes()
        return total

    def state(self) -> dict:
        """What this memory holds and where, for a person to look at."""
        out = {"reach": self.reach, "moments": len(self.rooms.moments), "rooms": len(self.rooms.rooms),
               "history_tokens": self.history_tokens(), "room_bytes": self.disk_bytes(),
               "folder_bytes": self.folder_bytes()}
        if self.vault is not None:
            out["vault"] = {"path": str(self.vault.path), "notes": len(self.vault)}
        if self.core is not None:
            out["core"] = {"tokens": self.core.tokens, "notes": list(self.core.members),
                           "left_out": list(self.core.left_out), "bytes": self.core.bytes}
        if self.tiers is not None:
            out["tiers"] = self.tiers.state()
        return out

    def save(self) -> None:
        """Save the index beside the rooms, the vault's index and the tiers' state."""
        self.rooms.save()
        if self.vault is not None:
            self.vault.save()
        if self.tiers is not None:
            self.tiers.save()

    def close(self) -> None:
        """Let go of the rooms. With any of the engine's layers on, everything is saved first, so nothing remembered
        is lost at closing; without them, closing is as it was (save first to keep the index)."""
        if self.vault is not None or self.tiers is not None or self.core is not None or self.meter is not None:
            self.rooms.save()
        if self.tiers is not None:
            self.tiers.save()
        if self.vault is not None:
            self.vault.save()
        self.rooms.close()

    # -- inside

    def _core(self, rec: Recall, core: Core | None) -> list:
        """The core's notes for the desk (written again first if its notes changed), as a list of zero or one."""
        if core is None:
            return []
        t = time.perf_counter()
        core.refresh()
        rec.seconds["core"] = time.perf_counter() - t
        rec.core = core.tokens if core.notes is not None else 0
        if self.tiers is not None:
            self.tiers.core_bytes = core.bytes
        return [core.notes] if core.notes is not None else []

    def _more(self, rec: Recall) -> dict:
        """What the new layers add to an answer's event (nothing when they are off)."""
        more = {}
        if self.tiers is not None:
            more.update(tier=rec.tier, asleep=rec.asleep, read_bytes=rec.read_bytes)
        if self.core is not None:
            more["core_tokens"] = rec.core
        if self.reach is not None:
            more["reach"] = self.reach
        return more

    def _note(self, m, date: dt.date | None, tags, pinned: bool):
        """A moment's vault note, with doors to the moments it shares a room with."""
        v = self.vault
        if date is None and v.epoch is not None:
            date = v.epoch + dt.timedelta(days=m.day)
        note = v.write(m.text, day=m.day, date=date, room=m.room, moment=m.mid, tags=tags, pinned=pinned)
        v.link_many(note.id, [v.moment_id(o) for o in self.rooms.rooms[m.room].members if o != m.mid], SHARE)
        return note

    @staticmethod
    def _join(a, b):
        import mlx.core as mx

        return mx.concatenate([a, b], axis=0)

    def _rewrite(self, rid: int) -> bytes:
        """A room's notes written again from its words, in one pass: the same as writing its moments one by one."""
        import mlx.core as mx

        notes = self.notebook.write(self.room_words(rid))
        return bytes(np.array(notes.view(mx.uint16)))

    def _strength(self, rid: int) -> float:
        """A room is as strong as its strongest note (all equal without a vault)."""
        if self.vault is None:
            return 1.0
        return max((self.vault.strength(self.vault.moment_id(m)) for m in self.rooms.rooms[rid].members), default=0.0)

    def _slept(self, rids: list[int], asleep: bool) -> None:
        if self.vault is not None:
            for rid in rids:
                for m in self.rooms.rooms[rid].members:
                    nid = self.vault.moment_id(m)
                    if nid in self.vault:
                        self.vault.update(nid, asleep=asleep)
        if self.log:
            self.log.write("sleep" if asleep else "wake", rooms=list(rids))
