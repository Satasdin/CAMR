"""The contenders the ruler measures. Each one is a memory approach in front of the same frozen reader.

A contender sees a life one day at a time (``observe``), may work at night (``sleep``), and is quizzed at the end of
each week (``begin_quiz``, then ``answer`` per question, then ``end_quiz``).
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

from engram.models import Reader, Reply
from engram.ruler.life import MONTHS, Day

SYSTEM = ("You are a personal assistant that remembers the user's own notes. Today is {today}. Answer the user's "
          "question in one short sentence, using only the notes below. If the notes do not contain the answer, "
          "reply exactly: I don't know.\n\nNotes:\n{notes}\nEnd of notes.")


def today_text(d: dt.date) -> str:
    return f"{d.strftime('%A')} {d.day} {MONTHS[d.month - 1]} {d.year}"


class Contender:
    name = "contender"

    def observe(self, day: Day) -> None:
        pass

    def sleep(self, day: Day) -> None:
        pass

    def begin_quiz(self, today: dt.date) -> None:
        self.today = today

    def answer(self, question: str) -> Reply:
        raise NotImplementedError

    def end_quiz(self) -> None:
        pass

    def disk_bytes(self) -> int:
        return 0

    def describe(self) -> dict:
        return {"name": self.name}

    def close(self) -> None:
        pass


class Bare(Contender):
    """The model alone, with no memory: the floor."""

    name = "bare"

    def __init__(self, reader: Reader):
        self.reader = reader

    def answer(self, question: str) -> Reply:
        return self.reader.generate(self.reader.chat_ids(SYSTEM.format(today=today_text(self.today), notes="(none)"),
                                                         question))

    def describe(self) -> dict:
        return {"name": self.name, "reader": self.reader.repo}


class Perfect(Contender):
    """Every note pasted in, read in full: the ceiling while the notes fit, and a measure of what that costs.

    Its notes are read once per quiz and kept as a cache for the 100 questions; ``read_s`` (that one reading) is
    added to each answer's wait, since a single question would have to read everything first."""

    name = "perfect"

    def __init__(self, reader: Reader, window: int = 32768):
        self.reader, self.window = reader, window
        self.notes: list[str] = []
        self.cache, self.head_len, self.read_s, self.fits = None, 0, 0.0, True

    def observe(self, day: Day) -> None:
        self.notes.extend(day.dated())

    def begin_quiz(self, today: dt.date) -> None:
        super().begin_quiz(today)
        system = SYSTEM.format(today=today_text(today), notes="\n".join(self.notes))
        head, _ = self.reader.split_ids(system, "?")
        self.system, self.head_len = system, len(head)
        self.fits = self.head_len + 200 <= self.window
        if self.fits:
            t = time.perf_counter()
            self.cache = self.reader.new_cache(head)
            self.read_s = time.perf_counter() - t

    def answer(self, question: str) -> Reply:
        if not self.fits:
            return Reply("(does not fit the model's window)", 0.0, 0.0, self.head_len, 0)
        _, rest = self.reader.split_ids(self.system, question)
        reply = self.reader.generate(rest, cache=self.cache)
        self.reader.rewind(self.cache, self.head_len)
        reply.ttft_s += self.read_s
        reply.prompt_tokens += self.head_len
        return reply

    def end_quiz(self) -> None:
        self.cache = None

    def describe(self) -> dict:
        return {"name": self.name, "reader": self.reader.repo, "window": self.window}


class CamrText(Contender):
    """The old CAMR (~/Desktop/camr-repo) exactly as CAMR Personal configured its engine: text notes found by
    similarity and words, gated, bridged by entity, dated, packed into a 512-token context.

    Only the models differ from the app: the shared MLX reader and embedder replace its Ollama ones, so the
    comparison is between memories, not models."""

    def __init__(self, reader: Reader, embedder, workdir: Path, min_similarity: float, token_budget: int = 512,
                 name: str = "camr"):
        import subprocess

        from camr.config import Config
        from camr.memory.clock import Clock
        from camr.memory.embedder import Embedder as CamrEmbedder
        from camr.memory.engine import MemoryEngine
        from camr.memory.store import SQLiteVectorStore
        from camr.models.tokenizer import RegexTokenizer

        class _Embedder(CamrEmbedder):
            def __init__(self, inner):
                self.inner, self.name, self.dim = inner, inner.name, inner.dim

            def encode(self, texts, *, is_query=False):
                return self.inner.encode(texts, is_query=is_query)

        class _Clock(Clock):
            def __init__(self):
                self.t = dt.datetime(2026, 1, 1, 12, tzinfo=dt.timezone.utc)

            def now(self):
                return self.t

        self.name, self.reader, self.min_similarity, self.token_budget = name, reader, min_similarity, token_budget
        self.clock = _Clock()
        workdir.mkdir(parents=True, exist_ok=True)
        self.path = workdir / "memory.sqlite"
        for p in workdir.glob("memory.sqlite*"):
            p.unlink()
        self.cfg = Config.from_dict({"memory": {
            "write_policy": "verbatim", "retrieval_policy": "similarity_only",
            "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0},
            "k": 20, "token_budget": token_budget, "min_similarity": min_similarity, "similarity_margin": 0.15,
            "expansion": "entity", "entity_gate": True, "chunk_tokens": 120, "keyword_k": 20,
            "dated_context": True, "time_filter": True, "entity_gate_skip_time": True, "profile": True,
            "aggregate": True, "slot_gate": True}})
        emb = _Embedder(embedder)
        self.store = SQLiteVectorStore(self.path, dim=emb.dim, embedder_name=emb.name)
        self.engine = MemoryEngine.from_config(self.cfg, store=self.store, embedder=emb, tokenizer=RegexTokenizer(),
                                               clock=self.clock)
        repo = Path(__import__("camr").__file__).resolve().parents[1]
        git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()
        self.camr_commit = git("rev-parse", "--short", "HEAD")
        self.camr_engine_dirty = bool(git("status", "--porcelain", "camr/memory"))

    def observe(self, day: Day) -> None:
        from camr.memory.note import Document

        self.clock.t = dt.datetime.combine(day.date, dt.time(20), tzinfo=dt.timezone.utc)
        self.engine.ingest([Document(dataset="life", doc_id=f"day{day.index}-{i}", text=t)
                            for i, t in enumerate(day.dated())])

    def begin_quiz(self, today: dt.date) -> None:
        super().begin_quiz(today)
        self.clock.t = dt.datetime.combine(today, dt.time(21), tzinfo=dt.timezone.utc)

    def notes_for(self, question: str) -> str:
        """The notes the old CAMR packs for a question, or "(none)" when it finds nothing."""
        rec = self.engine.recall(question, touch=False)
        return rec.context.strip() if not rec.abstained and rec.context.strip() else "(none)"

    def answer(self, question: str) -> Reply:
        t = time.perf_counter()
        notes = self.notes_for(question)
        recall_s = time.perf_counter() - t
        reply = self.reader.generate(self.reader.chat_ids(SYSTEM.format(today=today_text(self.today), notes=notes),
                                                          question))
        reply.ttft_s += recall_s
        return reply

    def disk_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.path.parent.glob("memory.sqlite*"))

    def describe(self) -> dict:
        return {"name": self.name, "reader": self.reader.repo, "min_similarity": self.min_similarity,
                "token_budget": self.token_budget, "camr_commit": self.camr_commit,
                "camr_engine_dirty": self.camr_engine_dirty, "memory_config": self.cfg.memory.__dict__
                if hasattr(self.cfg.memory, "__dict__") else str(self.cfg.memory)}

    def close(self) -> None:
        self.store.conn.close()


class Engram(Contender):
    """Engram, step 1: moments become notes in rooms on the SSD; a question lays the one room it is about on the desk,
    already read, and re-reads the moments closest to it as words.

    With ``words=True`` it is the same memory read entirely as text: the same room and moments are chosen, but the
    model reads the room's words instead of its saved notes. The pair measures what the notes are worth."""

    def __init__(self, reader: Reader, embedder, workdir: Path, *, words: bool = False, **settings):
        import shutil

        from engram.memory import Memory

        self.name = "engram-words" if words else "engram"
        self.reader, self.words = reader, words
        shutil.rmtree(workdir, ignore_errors=True)  # a run starts with an empty memory
        self.memory = Memory(reader, embedder, workdir, **settings)

    def observe(self, day: Day) -> None:
        for text in day.dated():
            self.memory.remember(text, day.index)

    def sleep(self, day: Day) -> None:
        self.memory.rooms.save()

    def answer(self, question: str) -> Reply:
        m = self.memory
        if not self.words:
            return m.answer(question, self.today)
        t = time.perf_counter()
        head, rest = m.prompt(self.today, question)
        rec = m.choose(question)
        ids = head + m.room_words(rec.room) + m.words(rec.closest) + rest
        before = time.perf_counter() - t
        reply = self.reader.generate(ids)
        reply.ttft_s += before
        return reply

    def disk_bytes(self) -> int:
        return self.memory.disk_bytes()

    def describe(self) -> dict:
        m = self.memory
        return {"name": self.name, "reader": self.reader.repo, "room_tokens": m.rooms.room_tokens,
                "join": m.rooms.join, "closest": m.closest, "allowance_bytes": m.allowance,
                "token_bytes": m.rooms.token_bytes, "event_log": m.log is not None}

    def close(self) -> None:
        self.memory.close()
