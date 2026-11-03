"""Engram's memory, step 1: every moment becomes notes in a room on the SSD; a question opens the one room it is
about and re-reads its few closest moments as words.

Remember: a moment is embedded, placed in the room holding its closest moment, and read by the model with that
room's earlier moments in view; its notes are appended to the room's file. Recall: the question is embedded; the
room holding its closest moment is read from the SSD in one burst and laid on the desk behind the header, already
read; the few moments closest to the question are then read as words, in date order, just before the question.

One room, not several: rooms written apart and laid side by side lose the thread, and a 1.7B model knew fewer facts
from three rooms' notes than from one room's notes plus its closest moments as words (DECISIONS.md, E-16).
"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from engram.events import EventLog, Looks, used
from engram.notes import Notebook
from engram.rooms import Rooms

INTRO = ("You are a personal assistant that remembers the user's own notes. Answer the user's question in one short "
         "sentence, using only the notes below. If the notes do not contain the answer, reply exactly: I don't know.")
_SLOT = "⁣NOTES⁣"  # where the room goes; never typed by a person

ROOM_TOKENS = 512  # at most 57 MB of notes on the 1.7B, inside the 256 MB allowance
JOIN = 0.80  # how close a moment must be to a room's closest moment to join it
CLOSEST = 4  # moments re-read as words after the room
ALLOWANCE_BYTES = 256 * 2**20


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


class Memory:
    def __init__(self, reader, embedder, path: Path, *, room_tokens: int = ROOM_TOKENS, join: float = JOIN,
                 closest: int = CLOSEST, allowance: int = ALLOWANCE_BYTES, log: bool = True):
        self.reader, self.embedder, self.closest, self.allowance = reader, embedder, closest, allowance
        self.log = EventLog(Path(path) / "events.jsonl") if log else None
        head, _ = self.prompt(dt.date(2026, 1, 1), "?")
        self.notebook = Notebook(reader, head)
        self.dtype = self.notebook.core[0][0].dtype
        if room_tokens * self.notebook.shape.token_bytes > allowance:
            raise ValueError("a full room must fit the allowance")
        self.rooms = Rooms(path, self.notebook.shape.token_bytes, room_tokens, join)

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

    def remember(self, text: str, day: int):
        import mlx.core as mx

        ids = self.ids(text)
        vec = self.embedder.encode_one(text)
        rid = self.rooms.place(vec, len(ids))
        after = None if rid is None else self._array(self.rooms.fetch([rid])[rid])
        notes = self.notebook.write(ids, after)
        m = self.rooms.add(text, day, vec, bytes(np.array(notes.view(mx.uint16))), rid)
        if self.log:
            self.log.write("remember", moment=m.mid, room=m.room, day=day, tokens=m.tokens, new_room=rid is None)
        return m

    def choose(self, question: str) -> Recall:
        """The room holding the moment closest to the question, and the closest moments overall."""
        t = time.perf_counter()
        if not self.rooms.moments:
            return Recall(None, [], 0, 0, seconds={"choose": time.perf_counter() - t})
        sims = self.rooms.vectors @ self.embedder.encode_one(question, is_query=True)
        order = np.argsort(-sims)
        room = self.rooms.rooms[self.rooms.moments[int(order[0])].room]
        closest = sorted(int(m) for m in order[:self.closest])
        return Recall(room.rid, closest, room.tokens, room.tokens * self.rooms.token_bytes,
                      seconds={"choose": time.perf_counter() - t})

    def recall(self, question: str) -> Recall:
        """Choose, read the room from the SSD in one burst, and lay it on the desk."""
        rec = self.choose(question)
        t = time.perf_counter()
        data = self.rooms.fetch([rec.room]) if rec.room is not None else {}
        rec.seconds["fetch"] = time.perf_counter() - t
        t = time.perf_counter()
        rec.desk = self.notebook.desk([self._array(data[rec.room])] if data else [])
        rec.seconds["desk"] = time.perf_counter() - t
        return rec

    def answer(self, question: str, today: dt.date, *, then: str = "", tools: list | None = None,
               max_tokens: int | None = None, kind: str = "answer", **extra):
        """Answer from the desk, and log what was picked up and how hard each written word looked at it."""
        t = time.perf_counter()
        head, rest = self.prompt(today, question, then, tools)
        rec = self.recall(question)
        ids = self.words(rec.closest) + rest
        spans = [] if rec.room is None else [(m, self.rooms.moments[m].start, self.rooms.moments[m].tokens)
                                             for m in self.rooms.rooms[rec.room].members]
        at = rec.tokens
        for m in rec.closest:  # re-read as words, after the room
            n = len(self.ids(self.rooms.moments[m].text))
            spans.append((m, at, n))
            at += n
        before = time.perf_counter() - t
        if self.log:
            with Looks(self.reader, self.notebook.p, spans, self.notebook.p + rec.tokens + len(ids), rec.desk) as looks:
                reply = self.reader.generate(ids, cache=rec.desk, max_tokens=max_tokens)
        else:
            reply = self.reader.generate(ids, cache=rec.desk, max_tokens=max_tokens)
        reply.ttft_s += before
        reply.prompt_tokens += len(head) + rec.tokens
        if self.log:
            per_word = looks.per_word(len(reply.pieces))
            share, use = used(per_word, looks.nodes)
            self.log.write(kind, question=question, room=rec.room, closest=rec.closest, nodes=looks.nodes,
                           share=share, used=use, words=reply.pieces,
                           looks=[[round(float(x), 4) for x in row] for row in per_word],
                           wait_s=round(reply.ttft_s, 4), seconds={k: round(v, 4) for k, v in rec.seconds.items()},
                           **extra)
        return reply

    def words(self, moments: list[int]) -> list[int]:
        return [i for m in moments for i in self.ids(self.rooms.moments[m].text)]

    def room_words(self, room: int | None) -> list[int]:
        """The room as words: what reading the text instead of the notes would cost."""
        return [] if room is None else self.words(self.rooms.rooms[room].members)

    def disk_bytes(self) -> int:
        return self.rooms.disk_bytes()

    def close(self) -> None:
        self.rooms.close()
