"""What a pairing remembers and recalls. The runtime runs its own model, so memory reaches it as words, not tensors.

A provider has two calls:
- ``recall_text(query, budget_tokens)``: the notes worth reading before ``query``, as text that fits the budget, or
  '' when there is nothing to add;
- ``remember(text, role)``: keep one turn of a finished exchange (``role`` is "user" or "assistant"). It may return
  how many characters of a long turn it left out (0 or None when it kept everything).

``VaultWords`` is the one that ships: words in a folder, found again by the engine's embedder.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

import numpy as np

from camr_engine.vault import Note, parse, render

PIECE_CHARS = 800  # a long turn is kept as pieces of at most this many characters, so one piece can fit a budget
TURN_PIECES = 16  # a turn keeps at most this many pieces, its first and last halves (a pasted file is not a note)
QUERY_CHARS = 2000  # what is embedded of a long question: its start and its end
LIMIT = 8  # notes recalled at most, however large the budget
WHO = {"user": "The user said", "assistant": "You answered"}
UNDATED = "Notes from camr_engine's own memory with no date, oldest first:"
REACH = "ollama"  # the reach written on the pairing's vault notes, and their ids' prefix
_DATED = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\]")  # how the app and the scripted lives start a moment's words
_EMPTY = np.zeros((0, 0), dtype=np.float32)


@runtime_checkable
class Provider(Protocol):
    def recall_text(self, query: str, budget_tokens: int) -> str: ...

    def remember(self, text: str, role: str) -> int | None: ...


class NoMemory:
    """Remembers nothing, so the proxy is a plain passthrough: the baseline for what the proxy itself costs."""

    def recall_text(self, query: str, budget_tokens: int) -> str:
        return ""

    def remember(self, text: str, role: str) -> int:
        return 0


def pieces(text: str, size: int = PIECE_CHARS) -> list[str]:
    """``text`` cut at paragraph breaks (inside a long paragraph, at spaces) into pieces of at most ``size`` chars."""
    parts = []
    for para in text.split("\n\n"):
        para = para.strip()
        while len(para) > size:
            cut = para.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            parts.append(para[:cut].strip())
            para = para[cut:].strip()
        if para:
            parts.append(para)
    out: list[str] = []
    for p in parts:
        if out and len(out[-1]) + 2 + len(p) <= size:
            out[-1] += "\n\n" + p
        else:
            out.append(p)
    return out


def clip(text: str, size: int = QUERY_CHARS) -> str:
    """``text`` when it is at most ``size`` characters, else its start and its end with a break between, ``size`` in
    all: a question is often at the end of what was pasted before it."""
    if len(text) <= size:
        return text
    head = (size - 2) // 2
    return f"{text[:head]}\n\n{text[len(text) - (size - 2 - head):]}"


def _name(embedder) -> str:
    return str(getattr(embedder, "name", type(embedder).__name__))


class VaultWords:
    """Memory as words in a folder, found again by the engine's embedder (Qwen3-Embedding through MLX).

    Each remembered turn is cut into pieces, and each piece is kept under ``<folder>/ollama/`` three ways: a line of
    ``notes.jsonl`` and a row of ``vectors.f32`` (both append-only, and what recall searches), and a note of its own
    in ``vault/``, in camr_engine.vault's format, so the folder opens in Obsidian. The vault's rule holds: the files are
    the truth. A note whose file a person deleted is never recalled again, and a note edited by hand is recalled with
    its new words (it is still found by its old ones, since its vector stays).

    When the folder is also an engine memory (``index.json`` from camr_engine.rooms), its moments' words are searched too,
    read-only, as the engine itself searches them. Notes a person wrote by hand in the engine's own ``vault/`` have
    no vector, so they are not searched.

    Recall takes the notes closest to the query that fit the budget, at most ``limit``, and puts them oldest first by
    date: a pairing note's time, or the ``[YYYY-MM-DD]`` an engine moment starts with. Engine moments with no date
    come last, under a heading of their own, since nothing places them among the dated ones.

    The embedder loads on first use, so making a VaultWords loads nothing. ``embedder`` may be any object with
    ``encode(texts, is_query=False)`` returning unit rows; tests pass a fake. Its ``name`` goes into ``meta.json``,
    and notes written by another embedder are refused, since their vectors would mean nothing to this one.
    """

    def __init__(self, folder: Path, embedder=None, *, limit: int = LIMIT, floor: float | None = None,
                 clock: Callable[[], dt.datetime] = dt.datetime.now, max_pieces: int = TURN_PIECES,
                 query_chars: int = QUERY_CHARS):
        self.folder, self.home = Path(folder), Path(folder) / "ollama"
        self._embedder, self.limit, self.floor, self.clock = embedder, limit, floor, clock
        self.max_pieces, self.query_chars = max(1, max_pieces), query_chars
        self.lock = threading.Lock()
        self.notes: list[dict] = []
        self.vectors = _EMPTY
        self.meta: dict = {}
        self._checked = False
        self._counts: dict[str, int] = {}
        self._engine: tuple[tuple, list[str], np.ndarray, list[str | None]] | None = None
        self._load()

    # --- the embedder, loaded on first use

    @property
    def embedder(self):
        if self._embedder is None:
            from camr_engine.models import Embedder

            self._embedder = Embedder()
        if not self._checked:
            stored = self.meta.get("embedder")
            if self.notes and stored and stored != _name(self._embedder):
                raise ValueError(f"the notes in {self.home} were embedded by {stored}, not {_name(self._embedder)}:"
                                 " their vectors mean nothing to it")
            self._checked = True
        return self._embedder

    def warm(self) -> None:
        """Load the embedder now, so the first chat does not wait for it, and check it wrote the notes kept here."""
        with self.lock:
            _ = self.embedder

    def tokens(self, text: str) -> int:
        """Tokens ``text`` takes, by the embedder's tokenizer when it has one (Qwen3's), else about 3 chars each."""
        n = self._counts.get(text)
        if n is None:
            tok = getattr(self._embedder, "tok", None)
            n = len(tok.encode(text)) if tok is not None else len(text) // 3 + 1
            self._counts[text] = n
        return n

    # --- on disk

    def note_file(self, nid: int) -> Path:
        """Where the note with id ``nid`` is kept for a person to read, edit or delete."""
        return self.home / "vault" / f"{REACH}-{nid:06d}.md"

    def _load(self) -> None:
        """Pick up the notes kept so far. After a crash between writes, what has no partner is cut off, so the
        notes and the vectors line up again."""
        notes_f, vec_f, meta_f = self.home / "notes.jsonl", self.home / "vectors.f32", self.home / "meta.json"
        lines = notes_f.read_text().splitlines() if notes_f.exists() else []
        for line in lines:
            try:
                self.notes.append(json.loads(line))
            except ValueError:  # a line cut short: it and anything after it are dropped
                break
        self.meta = json.loads(meta_f.read_text()) if meta_f.exists() else {}
        dim = int(self.meta.get("dim") or 0)
        flat = np.fromfile(vec_f, dtype=np.float32) if vec_f.exists() and dim else np.zeros(0, dtype=np.float32)
        rows = min(len(self.notes), flat.size // dim) if dim else 0
        self.notes = self.notes[:rows]
        if rows:
            self.vectors = flat[:rows * dim].reshape(rows, dim)
        if len(lines) > rows:
            notes_f.write_text("".join(json.dumps(n, ensure_ascii=False) + "\n" for n in self.notes))
        if vec_f.exists() and vec_f.stat().st_size > rows * dim * 4:
            os.truncate(vec_f, rows * dim * 4)

    def _engine_words(self) -> tuple[list[str], np.ndarray, list[str | None]]:
        """The engine memory's moments in this folder: their words, vectors and dates. They are read again whenever
        either file has changed, and kept only once the two agree (``Rooms.save`` writes one, then the other)."""
        index, vec_f = self.folder / "index.json", self.folder / "vectors.npy"
        try:
            a, b = index.stat(), vec_f.stat()
        except FileNotFoundError:
            return [], _EMPTY, []
        key = (a.st_mtime_ns, b.st_mtime_ns, b.st_size)
        if self._engine is not None and self._engine[0] == key:
            return self._engine[1:]
        try:
            texts = [m["text"] for m in json.loads(index.read_text()).get("moments", [])]
            vecs = np.load(vec_f).astype(np.float32)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):  # caught mid-save: try again next time
            return self._engine[1:] if self._engine is not None else ([], _EMPTY, [])
        if vecs.ndim != 2:
            vecs = _EMPTY
        n = min(len(texts), len(vecs))
        dates = [(d.group(1) if (d := _DATED.match(t)) else None) for t in texts[:n]]
        got = (texts[:n], vecs[:n], dates)
        if len(texts) == len(vecs):
            self._engine = (key, *got)
        return got

    def _words(self, note: dict) -> str:
        """A note's words as its file says now: '' when a person deleted the file (the note is forgotten)."""
        f = self.note_file(note["id"])
        try:
            return (parse(f.stem, f.read_text(encoding="utf-8")).text or "").strip()
        except FileNotFoundError:
            return ""
        except (OSError, UnicodeDecodeError):  # unreadable just now: the words as they were kept
            return note["text"]

    def _write_note(self, note: dict, at: dt.datetime) -> None:
        f = self.note_file(note["id"])
        f.parent.mkdir(parents=True, exist_ok=True)
        page = Note(id=f.stem, text=note["text"], date=at.date().isoformat(), reach=REACH,
                    tags=[REACH, note["role"]], extra={"time": f"{at:%H:%M}"})
        tmp = f.parent / f".{f.name}.tmp"
        tmp.write_text(render(page), encoding="utf-8")
        os.replace(tmp, f)

    # --- the provider

    def remember(self, text: str, role: str) -> int:
        """Keep one turn. A turn longer than ``max_pieces`` pieces keeps its first and last pieces only; returns how
        many characters were left out. Nothing is written when the embedder is not the one that wrote the notes."""
        text = text.strip()
        if not text:
            return 0
        with self.lock:
            at = self.clock().replace(microsecond=0)
            cut = pieces(text)
            left = 0
            if len(cut) > self.max_pieces:
                head, tail = self.max_pieces // 2, len(cut) - (self.max_pieces - self.max_pieces // 2)
                left = sum(len(p) for p in cut[head:tail])
                cut = cut[:head] + cut[tail:]
            vecs = np.asarray(self.embedder.encode(cut), dtype=np.float32)
            if vecs.ndim != 2 or len(vecs) != len(cut):
                raise ValueError(f"the embedder gave {vecs.shape} for {len(cut)} pieces")
            if self.notes and vecs.shape[1] != self.vectors.shape[1]:
                raise ValueError(f"the embedder gives {vecs.shape[1]} numbers per note, the notes in {self.home} "
                                 f"have {self.vectors.shape[1]}")
            self.home.mkdir(parents=True, exist_ok=True)
            if not self.notes:
                self.meta = {"dim": int(vecs.shape[1]), "embedder": _name(self.embedder)}
                (self.home / "meta.json").write_text(json.dumps(self.meta))
            first = len(self.notes)
            new = [{"id": first + k, "at": at.isoformat(), "role": role, "text": p} for k, p in enumerate(cut)]
            for note in new:  # the files first: a note in notes.jsonl without its file was deleted by a person
                self._write_note(note, at)
            with (self.home / "vectors.f32").open("ab") as out:  # then vectors: a crash leaves no note unfound
                out.write(vecs.tobytes())
            with (self.home / "notes.jsonl").open("a") as out:
                out.write("".join(json.dumps(n, ensure_ascii=False) + "\n" for n in new))
            self.notes += new
            self.vectors = vecs if not self.vectors.size else np.concatenate([self.vectors, vecs])
            return left

    def recall_text(self, query: str, budget_tokens: int) -> str:
        query = clip(query.strip(), self.query_chars)
        if not query or budget_tokens <= 0:
            return ""
        with self.lock:
            texts, engine, dates = self._engine_words()
            if not engine.size and not self.vectors.size:
                return ""
            q = np.asarray(self.embedder.encode([query], is_query=True)[0], dtype=np.float32)
            if not engine.size or engine.shape[1] != q.size:  # words from another embedder are skipped
                texts, engine, dates = [], _EMPTY, []
            own = self.vectors if self.vectors.size and self.vectors.shape[1] == q.size else _EMPTY
            if not engine.size and not own.size:
                return ""
            split = len(engine)
            sims = np.concatenate([m for m in (engine, own) if m.size]) @ q
            chosen, used = [], 0  # (date, place, words)
            for i in np.argsort(-sims)[:self.limit * 8]:  # past this, the notes are too far to be worth counting
                if len(chosen) == self.limit or (self.floor is not None and sims[i] < self.floor):
                    break
                i = int(i)
                if i < split:
                    line, when = texts[i], dates[i]
                else:
                    note = self.notes[i - split]
                    words = self._words(note)
                    if not words:
                        continue
                    line, when = self._line(note, words), note["at"]
                n = self.tokens(line)
                if used + n <= budget_tokens:
                    chosen.append((when, i, line))
                    used += n
            dated = sorted((c for c in chosen if c[0]), key=lambda c: (c[0], c[1]))
            undated = sorted((c for c in chosen if not c[0]), key=lambda c: c[1])
            if not dated or not undated:  # one order holds for all of them: by date, or as they were told
                return "\n\n".join(c[2] for c in (dated or undated))
            return "\n\n".join([c[2] for c in dated] + [UNDATED] + [c[2] for c in undated])

    @staticmethod
    def _line(note: dict, words: str | None = None) -> str:
        at = note["at"].replace("T", " ")[:16]
        return f"[{at}] {WHO.get(note['role'], note['role'])}: {note['text'] if words is None else words}"
