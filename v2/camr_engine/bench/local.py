"""The local contenders, run with MLX on this Mac, and the Long Haul runner for them.

- ``engine:<model>`` is the memory engine: one camr_engine.memory.Memory over one project reach's folder
  (``<folder>/project/longhaul``, locked as reach.Session locks it), with the vault, the core, the tiers and the
  metrics on, and driven as reach.Session drives one reach: choose the room, then answer from it. Hot rooms get 2 GB
  of RAM and the room files 40 GB of disk. When the disk budget is full, the weakest rooms sleep and are answered from
  their words. Models: qwen3-1.7b, qwen3-4b and qwen3-8b, with the Qwen3-Embedding-0.6B embedder.
- ``words:<model>`` is memory read as words, for qwen-27b, whose linear-attention layers keep no keys and values to
  save. It takes ruler.contenders.CamrWords's approach: the engine's rooms (the same embedder, the same 512-token
  cap counted in the 1.7B's tokens, the same join), the same choice per question, pasted in as text.
- ``bare:<model>`` has no memory: the most recent W tokens of the history are the context. W is each model's window,
  capped so its keys and values fit in 24 GB: 32K for the 1.7B and 8B, 64K for the 4B, 16K for the 27B. The window
  is read once per checkpoint; each question is appended, answered, and cut off again, so a question costs only
  itself. Reading the window is counted as the checkpoint's ingest, not as any answer's time.

A moment is one event's words with its date, as the ruler dates its notes (``[YYYY-MM-DD] text``). The Long Haul asks
about "day 50", so the engine's moments also carry the day number (``[YYYY-MM-DD, day 50] text``), and the day's own
line is not kept as a moment of its own, since every moment carries it. Bare reads the history as it is, day lines
included, as Claude does.

The questions never change the engine's memory (``learn`` off): each is answered from the memory as the telling left
it. The room it read is not kept hot afterwards, its use is not counted as recent, and no moment gains strength. So a
probe asked again at a later checkpoint gets no rehearsal that bare and Claude never get. The attention watch
(events.Looks, as the app runs it) is off (``watch``): it keeps every written word's keys alive, which made a
575-token page answer peak at 10.1 GB against 4.1 GB for short ones. Each answer is still logged, without its looks.

The Long Haul's wording. Bare reads the yardstick's instructions and opener (camr_engine.bench.claude), its history lines
joined by a blank line as Claude's are. The engine and words read the same instructions with the history's notes in
place of the history (``LONGHAUL_INTRO``, the words the Ollama pairing's paired contender reads), then the notes,
"Today is <date>." and the family's one line on the form of its answer. Bare gets that line after the question. Every
record's ``contender`` holds the whole system text, where the line goes and whether a date line is given. The suites
(camr_engine.bench.suite_run) do not run local contenders yet: they need a suite frame without the Long Haul's wording.

Every local model answers with Qwen3's thinking off (``enable_thinking=False``). Each family gets one line on the
form of its answer (an HTML document, a Python block, the working and then the number); nothing about its content.

    python -m camr_engine.bench.local longhaul --contender engine:qwen3-1.7b --dir work/haul/s1 [--cuts 64K 256K] [--limit 5]
    python -m camr_engine.bench.local speed --contender engine:qwen3-1.7b --dir work/haul/s1

``speed`` ingests the Long Haul once and, as the memory reaches 1K, 10K and 100K moments (and at the end), asks a
few short questions and records retrieval ms, bytes read, GB/s and the time to the first word, with the ingest
throughput and the disk used. Memories go under work/memories/, in folders ending ``.nosync`` so iCloud leaves the
room files alone. A contender that fails is recorded as failed and the next one runs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import gc
import json
import os
import random
import re
import shutil
import time
from collections import Counter, OrderedDict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from camr_engine.bench.contender import (METRICS, OTHER_TOKENS, RECORDS, THINKING, Answer, Contender, _footprint_gb, ask_all,
                                    decode_tps, max_tokens, metrics, record_path, run, slug, stamp, summarize,
                                    write_record, environment)
from camr_engine.memory import _SLOT, INTRO, Memory, today_text
from camr_engine.metrics import folder_bytes
from camr_engine.notes import Shape
from camr_engine.swap import Tiers

MODELS = {"qwen3-1.7b": "mlx-community/Qwen3-1.7B-4bit",
          "qwen3-4b": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
          "qwen3-8b": "mlx-community/Qwen3-8B-4bit",
          "qwen-27b": "mlx-community/Qwen3.8-27B-4bit"}
EMBEDDER = "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"
NO_KV = {"qwen-27b"}  # hybrid attention: its linear layers keep a running state, not keys and values
WINDOWS = {"qwen3-1.7b": 32_768, "qwen3-4b": 65_536, "qwen3-8b": 32_768, "qwen-27b": 16_384}
KINDS = ("engine", "words", "bare", "rag")
RAG_K = 8  # conventional RAG: the closest moments pasted in as text (the app's chat route, RAG_K)…
RAG_TOKENS = 1024  # …up to this many tokens: the memory CAMR's desk holds, one room (at most 512) + 4 closest moments
RAG_ORDERS = ("date", "score")

RAM_BYTES = 2 * 10**9  # hot rooms and the core
DISK_BYTES = 40 * 10**9  # awake room files
PROJECT = "longhaul"
NAP_DAYS = 5  # a nap (fade, then hold the disk budget, then save) every working week
MARKS = (1_000, 10_000, 100_000)  # moments at which ``speed`` takes a point
SPEED_QUESTIONS = 5
SHORT = ("fact", "changed", "two_hop", "lookalike", "never")  # families with short answers, for speed points

WORK = Path(__file__).resolve().parents[3] / "work"
MEMORIES = WORK / "memories"
HAUL = WORK / "haul" / "s1"

# The form of an answer, by family. Only the form: what goes in it comes from memory.
HINTS = {"page": "Reply with the page as one complete HTML document in a ```html block, its CSS included.",
         "code": "Reply with the code in one ```python block.",
         "maths": "Show the working in a few short steps, then give the final number on the last line."}
# The yardstick's own instructions (camr_engine.bench.claude.SYSTEM and OPENER), so bare reads the history as Claude does.
BARE_SYSTEM = ("You answer questions about a project's history: one developer's log of chats, decisions, code, notes "
               "and lessons, oldest first. Answer from the history only. When the history never says, answer \"I "
               "don't know\". Keep each answer short unless the question asks for code or a page.")
OPENER = "The project history, oldest first:\n<history>\n"
JOIN_LINES = "\n\n"  # the yardstick joins history lines with a blank line
# The same instructions for memory read as notes: the Ollama pairing's (camr_engine.bench.ollama_run.PAIRED_SYSTEM).
LONGHAUL_INTRO = ("You answer questions about a project's history: one developer's log of chats, decisions, code, "
                  "notes and lessons. Notes from that history come before each question. Answer from them only. When "
                  "they never say, answer \"I don't know\". Keep each answer short unless the question asks for code "
                  "or a page.")
NOTES_PROMPT = ("system: the instructions, then \"Notes:\" with the core, the room and the closest moments, \"End of "
                "notes.\", \"Today is <date>.\" and the family's line; user: the question")
DAY_LINE = re.compile(r"^Day \d+ · [A-Z][a-z]+ \d{1,2} [A-Z][a-z]+ \d{4}$")


def hint(family: str | None) -> str:
    return HINTS.get(family or "", "")


def view(*, prefill: int, notes: int, words: int) -> dict:
    """What one answer had in front of it, the same keys for every contender: ``prefill_tokens`` read as text this
    answer (memory, instructions and question), ``memory_notes`` tokens of memory already read (notes), and
    ``memory_words`` tokens of memory read as text; ``memory_in_view`` is the two together."""
    return {"prefill_tokens": int(prefill), "memory_notes": int(notes), "memory_words": int(words),
            "memory_in_view": int(notes) + int(words)}


def _peak_footprint_gb() -> float | None:
    from camr_engine.models import peak_footprint_bytes

    got = peak_footprint_bytes()
    return round(got / 1e9, 3) if got is not None else None


def parse(spec: str) -> tuple[str, str]:
    """``engine:qwen3-1.7b`` -> ("engine", "qwen3-1.7b"), checked."""
    kind, _, model = spec.partition(":")
    if kind not in KINDS:
        raise ValueError(f"a local contender is one of {', '.join(k + ':<model>' for k in KINDS)}, not {spec!r}")
    if model not in MODELS:
        raise ValueError(f"the local models are {', '.join(MODELS)}, not {model!r}")
    if kind == "engine" and model in NO_KV:
        raise ValueError(f"{model} keeps no keys and values in its linear-attention layers: use words:{model}")
    return kind, model


def kv_shape(config: dict) -> Shape:
    """One token's notes as the Notebook derives them from the model: every layer's keys and values."""
    c = config if "num_hidden_layers" in config else config.get("text_config", config)
    head_dim = c.get("head_dim") or c["hidden_size"] // c["num_attention_heads"]
    return Shape(int(c["num_hidden_layers"]), int(c["num_key_value_heads"]), int(head_dim),
                 float(c.get("rope_theta") or 0.0))


def config_of(repo: str) -> dict | None:
    """A model's config from the local Hugging Face cache (never the weights), or None when it is not there."""
    try:
        from huggingface_hub import try_to_load_from_cache

        path = try_to_load_from_cache(repo, "config.json")
    except Exception:  # noqa: BLE001: no hub library, or no cache
        return None
    return json.loads(Path(path).read_text()) if isinstance(path, str) else None


def haul_dates() -> Callable[[int], dt.date]:
    """The Long Haul's working days: day 1 is its first."""
    from camr_engine.bench.haul.script import LONGEST, calendar

    days = calendar(LONGEST)  # the 110 days, and the days a longer script adds after them
    return lambda day: days[min(max(day, 1), len(days)) - 1]


def peak_reset() -> None:
    from camr_engine.models import peak_reset as reset

    reset()


def peak_gb() -> float | None:
    from camr_engine.models import peak_gb as peak

    got = peak()
    return round(got, 3) if got is not None else None


class Loader:
    """The models a run needs, each loaded once and shared by the contenders that use it. A new reader lets go of the
    one before, so two big readers are never in memory together. Each reader writes a few words once, untimed, right
    after loading: the first generation is slow (5.5 s to the first word in the 64K smoke, against 0.1 to 0.25 s for
    the rest), and no question should pay for it."""

    def __init__(self):
        self.readers: dict[str, Any] = {}
        self.warm_s: dict[str, float] = {}
        self._embedder = None

    def reader(self, repo: str):
        if repo not in self.readers:
            self.readers.clear()
            gc.collect()
            try:
                import mlx.core as mx

                mx.clear_cache()
            except ImportError:
                pass
            from camr_engine.models import Reader

            reader = Reader(repo, max_tokens=OTHER_TOKENS)
            t = time.perf_counter()
            reader.generate(reader.chat_ids("Reply with one word.", "Ready?"), max_tokens=4)
            self.warm_s[repo] = round(time.perf_counter() - t, 3)
            self.readers[repo] = reader
        return self.readers[repo]

    def embedder(self):
        if self._embedder is None:
            from camr_engine.models import Embedder

            self._embedder = Embedder(EMBEDDER)
        return self._embedder


def _fresh(folder: Path) -> Path:
    folder = Path(folder)
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _hold(folder: Path) -> int:
    """The reach's lock file, held as reach.Session holds it, so the app cannot open this memory meanwhile."""
    fd = os.open(Path(folder) / ".lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError(f"the memory at {folder} is open in another process") from None
    return fd


def _unused(moments, today=None, day=None) -> None:
    """Memory.use while the bench asks: the moments an answer used gain nothing."""


class _Days:
    """The day each event was told on, turned into a date, and the moment's words as the ruler dates them."""

    def __init__(self, dates: Callable[[int], dt.date] | None, day_numbers: bool):
        self.dates, self.day_numbers = dates or haul_dates(), day_numbers
        self.day: int | None = None
        self.today: dt.date | None = None

    def moment(self, text: str, day: int) -> str | None:
        """The moment to keep for one event, or None for a day line already carried by every moment."""
        self.day, self.today = day, self.dates(day)
        if self.day_numbers and DAY_LINE.match(text):
            return None
        return stamp(text, self.today, day if self.day_numbers else None)

    def now(self) -> dt.date:
        return self.today or self.dates(1)

    def reset(self) -> None:
        self.day = self.today = None


class _Memory(Memory):
    """camr_engine.memory.Memory with its instructions given: ``intro`` in place of memory.INTRO, and nothing else
    changed. With INTRO it is Memory itself, prompt for prompt."""

    def __init__(self, *args, intro: str = INTRO, **kw):
        self.intro = intro
        super().__init__(*args, **kw)

    def prompt(self, today: dt.date, question: str, then: str = "", tools: list | None = None
               ) -> tuple[list[int], list[int]]:
        if self.intro == INTRO:
            return super().prompt(today, question, then, tools)
        system = (f"{self.intro}\n\nNotes:\n{_SLOT}End of notes.\nToday is {today_text(today)}."
                  + (f"\n\n{then}" if then else ""))
        text = self.reader.tok.apply_chat_template([{"role": "system", "content": system},
                                                    {"role": "user", "content": question}], tools=tools,
                                                   add_generation_prompt=True, enable_thinking=THINKING,
                                                   tokenize=False)
        head, rest = text.split(_SLOT)
        return self.reader.tok.encode(head), self.reader.tok.encode(rest)


class Engine(Contender):
    """engine:<model>: the memory engine over one project reach.

    ``intro`` is the instructions (memory.INTRO by default; the Long Haul passes LONGHAUL_INTRO). ``learn`` lets
    questions change the memory, as they do in the app: the room read stays hot and counts as recently used, and,
    with ``watch``, the moments an answer used gain strength. ``watch`` records how hard each written word looks at
    each moment (events.Looks; it needs ``log``)."""

    def __init__(self, model: str, *, loader: Loader | None = None, reader=None, embedder=None,
                 ram_bytes: int = RAM_BYTES, disk_bytes: int = DISK_BYTES, project: str = PROJECT,
                 dates: Callable[[int], dt.date] | None = None, day_numbers: bool = True,
                 nap_days: int | None = NAP_DAYS, intro: str = INTRO, learn: bool = False, watch: bool = False,
                 log: bool = True, wake: bool = False, snapshots: Path | None = None, **settings):
        if reader is None:
            parse(f"engine:{model}")
        self.snapshots = snapshots
        self.model, self.repo, self.name = model, MODELS.get(model), f"engine:{model}" + ("+wake" if wake else "")
        self.loader, self._reader, self._embedder = loader or Loader(), reader, embedder
        self.ram_bytes, self.disk_bytes, self.project = ram_bytes, disk_bytes, project
        self.days, self.nap_days, self.settings = _Days(dates, day_numbers), nap_days, settings
        self.intro, self.learn, self.log, self.wake = intro, learn, log, wake
        self.watch = bool(watch and log)  # the watch writes into the event log: without it nothing is watched
        self.memory: _Memory | None = None
        self.folder: Path | None = None
        self._lock: int | None = None
        self._reset()

    def _reset(self) -> None:
        self.moments, self.remember_s, self.saves_s = 0, 0.0, 0.0
        self.naps = {"count": 0, "seconds": 0.0, "faded_notes": 0, "slept_rooms": 0}
        self._napped: int | None = None
        self._dirty = False
        self.days.reset()

    def open(self, folder: Path) -> None:
        self.close()  # a contender opened again (a suite's next group) lets go of the memory before
        folder = _fresh(folder)
        self._reset()
        self._make(folder / "project" / self.project)  # where reach.Session keeps a project reach

    def attach(self, snap: Path, day: int) -> None:
        """Open a memory told earlier (``<snap>/project/<project>``, as ``snapshots`` keeps them) as of ``day``, to be
        asked only: nothing is told and nothing is cleared."""
        self.close()
        self._reset()
        folder = Path(snap) / "project" / self.project
        if not (folder / "index.json").exists():
            raise FileNotFoundError(f"no memory at {folder}")
        self._make(folder)
        self.days.day, self.days.today = day, self.days.dates(day)
        self.moments = len(self.memory.rooms.moments)

    def _make(self, folder: Path) -> None:
        reader = self._reader or self.loader.reader(self.repo)
        embedder = self._embedder or self.loader.embedder()
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self._lock = _hold(self.folder)
        try:
            self.memory = _Memory(reader, embedder, self.folder, intro=self.intro, reach=f"project:{self.project}",
                                  vault=True, core=True,
                                  tiers=Tiers(ram_bytes=self.ram_bytes, disk_bytes=self.disk_bytes, wake=self.wake),
                                  metrics=True, log=self.log, **self.settings)
            config = config_of(self.repo) if self.repo else None
            if config is not None and kv_shape(config) != self.memory.notebook.shape:
                raise ValueError(f"the notes' shape {self.memory.notebook.shape} is not the one {self.repo}'s "
                                 f"config gives, {kv_shape(config)}")
        except BaseException:
            self.close()
            raise

    def cut_told(self, checkpoint: dict) -> None:
        """A checkpoint's events are all told: with ``snapshots``, save the memory and keep an APFS clone of it
        (``<snapshots>/<cut>.nosync``, with ``snapshot.json``), so other ways of reading it can be asked later
        (camr_engine.bench.desk). The clone is not counted as ingest."""
        if not self.snapshots or self.memory is None:
            return
        import subprocess

        self.memory.save()
        root = self.folder.parent.parent  # the folder the run gave: <root>/project/<project>
        snap = Path(self.snapshots) / f"{checkpoint['name']}.nosync"
        if snap.exists():
            raise FileExistsError(f"{snap} is already kept")
        snap.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cp", "-c", "-R", str(root), str(snap)], check=True)
        (snap / "snapshot.json").write_text(json.dumps(
            {"cut": checkpoint["name"], "events": checkpoint["events"], "tokens": checkpoint.get("tokens"),
             "day": self.days.day, "today": str(self.days.now()), "moments": self.moments, "contender": self.name}))

    def tell(self, text: str, day: int) -> None:
        if self.nap_days and self._napped is not None and day - self._napped >= self.nap_days:
            self.nap(day)
        if self._napped is None:
            self._napped = day
        moment = self.days.moment(text, day)
        if moment is None:
            return
        t = time.perf_counter()
        self.memory.remember(moment, day, date=self.days.today)
        self.remember_s += time.perf_counter() - t
        self.moments += 1
        self._dirty = True

    def nap(self, day: int) -> None:
        """Fade the vault up to ``day``, hold the disk budget with the new strengths, and save."""
        t = time.perf_counter()
        changed, slept = self.memory.fade(day)
        self.memory.save()
        self.naps["count"] += 1
        self.naps["seconds"] = round(self.naps["seconds"] + time.perf_counter() - t, 3)
        self.naps["faded_notes"] += changed
        self.naps["slept_rooms"] += len(slept)
        self._napped, self._dirty = day, False

    @contextmanager
    def _asking(self) -> Iterator[Any]:
        """One question as the bench asks it; yields the event log (or None).

        Unless ``learn``: the tiers' recency, the hot rooms and their order are put back afterwards, and no moment
        gains strength. The tiers' hit counts are put back either way, so they count only the telling's reads.
        Unless ``watch``: the event log is held back during the answer, so nothing watches its attention."""
        m = self.memory
        tiers, log = m.tiers, m.log
        hits = Counter(tiers.hits)
        kept = None if self.learn else (dict(tiers.used), tiers.tick, OrderedDict(tiers.pool.hot),
                                        dict(tiers.pool.sizes))
        if not self.watch:
            m.log = None
        elif not self.learn:
            m.use = _unused  # shadows Memory.use on this one memory: watched, logged as used, strengthened never
        try:
            yield log
        finally:
            m.log = log
            m.__dict__.pop("use", None)
            tiers.hits = hits
            if kept is not None:
                tiers.used, tiers.tick = kept[0], kept[1]
                tiers.pool.hot, tiers.pool.sizes = kept[2], kept[3]
                tiers.pool.fit()

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        if self._dirty:  # the index is saved before a question, never during one
            t = time.perf_counter()
            self.memory.save()
            self.saves_s += time.perf_counter() - t
            self._dirty = False
        today, day = self.days.now(), self.days.day
        peak_reset()
        with self._asking() as log:
            t = time.perf_counter()  # as reach.Session.answer: the wait counts the choosing
            rec = self.memory.choose(question)
            reply = self.memory.answer(question, today, then=hint(family), max_tokens=max_tokens, chosen=rec,
                                       started=t, day=day, record=True, family=family)
        peak = peak_gb()
        if log is not None and not self.watch:  # the answer, as Memory logs it, without looks
            log.write("answer", question=question, room=rec.room, closest=rec.closest, words=reply.pieces,
                      wait_s=round(reply.ttft_s, 4), seconds={k: round(v, 4) for k, v in rec.seconds.items()},
                      tier=rec.tier, asleep=rec.asleep, read_bytes=rec.read_bytes, core_tokens=rec.core,
                      reach=rec.reach, family=family, watched=False)
        return self._answer(rec, reply, peak)

    def _answer(self, rec, reply, peak: float | None) -> Answer:
        """One answer as the bench records it, from the room chosen and the reply."""
        r = reply.metrics
        m = metrics(ttft_s=r.first_word_s, total_s=r.total_s, prefill_tps=r.prefill_tps,
                    decode_tps=decode_tps(r.answer_tokens, r.total_s, r.first_word_s),
                    retrieval_ms=r.retrieval_ms.get("total"), bytes_read=r.read_bytes, gbps=r.gbps,
                    read_share=r.read_share, context_tokens=r.context_tokens, history_tokens=r.history_tokens,
                    peak_ram_gb=None if self.watch else peak, disk_gb=round(r.disk_bytes / 1e9, 6), tier=r.tier)
        extra = {"retrieval_steps_ms": r.retrieval_ms, "room": r.room, "new_tokens": r.new_tokens,
                 "answer_tokens": r.answer_tokens, "mlx_decode_tps": r.decode_tps,
                 "rss_peak_gb": round(r.peak_ram_bytes / 1e9, 3), "asleep": rec.asleep, "core_tokens": rec.core,
                 "score": round(rec.score, 4) if rec.score is not None else None,
                 "rooms_laid": len(rec.laid), **view(prefill=r.new_tokens, notes=rec.core + rec.notes,
                                                    words=rec.words)}
        if self.watch:  # the watch's own keys are in this peak: see the module's docstring
            extra["peak_ram_gb_watched"] = peak
        return Answer(reply.text, m, extra)

    def reading_s(self) -> float:
        return self.saves_s

    def status(self) -> dict:
        if self.memory is None:
            return {}
        st = self.memory.state()
        tiers = st.get("tiers", {})
        return {"moments": st["moments"], "rooms": st["rooms"], "history_tokens": st["history_tokens"],
                "awake_rooms": tiers.get("ssd", {}).get("rooms"), "asleep_rooms": len(tiers.get("vault", {})
                                                                                      .get("rooms", [])),
                "hot_rooms": len(tiers.get("ram", {}).get("rooms", [])),
                "ram_used_bytes": tiers.get("ram", {}).get("used_bytes"),
                "disk_awake_bytes": tiers.get("ssd", {}).get("used_bytes"), "folder_bytes": st["folder_bytes"],
                "disk_gb": round(st["folder_bytes"] / 1e9, 6), "vault_notes": st.get("vault", {}).get("notes"),
                "core_tokens": self.memory.core.tokens if self.memory.core is not None else 0,
                "token_bytes": self.memory.rooms.token_bytes,
                "bits": self.memory.rooms.bits,
                "join_hits": tiers.get("hits", {}),  # rooms read to append a moment; questions' tiers are per answer
                "remember_s": round(self.remember_s, 3), "saves_s": round(self.saves_s, 3), "naps": dict(self.naps),
                "peak_footprint_gb": _peak_footprint_gb()}

    def describe(self) -> dict:
        from camr_engine.memory import CLOSEST, DESK_ROOMS, FINDER, JOIN, ROOM_TOKENS

        shape = self.memory.notebook.shape if self.memory is not None else (
            kv_shape(config_of(self.repo)) if self.repo and config_of(self.repo) else None)
        return {"name": self.name, "kind": "engine", "model": self.model, "repo": self.repo, "embedder": EMBEDDER,
                "reach": f"project:{self.project}",
                "drives": "camr_engine.memory.Memory at <folder>/project/<project>, as reach.Session drives one reach: "
                          "choose, then answer with record=True",
                "layers": ["rooms", "vault", "core", "tiers", "metrics"],
                "core": "on, empty: every moment is told untagged, and the core holds only notes tagged core",
                "ram_bytes": self.ram_bytes, "disk_bytes": self.disk_bytes, "wake": self.wake,
                "room_tokens": self.settings.get("room_tokens", ROOM_TOKENS), "join": self.settings.get("join", JOIN),
                "closest": self.settings.get("closest", CLOSEST),
                "desk_rooms": self.settings.get("desk_rooms", DESK_ROOMS),
                "desk_tokens": self.settings.get("desk_tokens"), "desk_order": self.settings.get("desk_order", "date"),
                "reread": self.settings.get("reread", "all"),
                "finder": self.settings.get("finder", FINDER),
                "kv_shape": None if shape is None else {"layers": shape.layers, "kv_heads": shape.kv_heads,
                                                        "head_dim": shape.head_dim, "rope_base": shape.rope_base,
                                                        "token_bytes": shape.token_bytes},
                "moment": "[YYYY-MM-DD, day N] text" if self.days.day_numbers else "[YYYY-MM-DD] text",
                "day_lines_kept": not self.days.day_numbers, "nap_days": self.nap_days, "enable_thinking": THINKING,
                "system": self.intro, "prompt": NOTES_PROMPT, "today_line": True,
                "hint_in": "system, after the notes and the date", "hints": HINTS,
                "writes": "Memory.remember for each moment; the index is saved at each nap and before a checkpoint's "
                          "first question (reach.Session.remember saves after every moment)",
                "questions": ("learn: each question leaves its room hot and recently used"
                              + (", and the moments it used stronger" if self.watch else "")) if self.learn else
                             "read-only: each question is answered from the memory as the telling left it",
                "watch": self.watch, "event_log": self.log,
                "peak_ram_gb": "in extra.peak_ram_gb_watched (the watch keeps every written word's keys)"
                               if self.watch else "MLX's peak over the answer, retrieval included"}

    def close(self) -> None:
        if self.memory is not None:
            try:
                self.memory.close()  # with the engine's layers on, it saves everything first
            finally:
                self.memory = None
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None


class Words(Contender):
    """words:<model>: the engine's rooms read as words, for a reader that cannot use saved notes. ``intro`` is the
    instructions, as the engine's (memory.INTRO by default)."""

    def __init__(self, model: str, *, loader: Loader | None = None, reader=None, embedder=None,
                 counter: Callable[[str], int] | None = None, dates: Callable[[int], dt.date] | None = None,
                 day_numbers: bool = True, intro: str = INTRO):
        if reader is None:
            parse(f"words:{model}")
        self.model, self.repo, self.name = model, MODELS.get(model), f"words:{model}"
        self.loader, self._reader, self._embedder, self._counter = loader or Loader(), reader, embedder, counter
        self.days, self.intro = _Days(dates, day_numbers), intro
        self.rooms = self.reader = self.embedder = self.count = None
        self.folder: Path | None = None
        self.moments, self.saves_s, self._dirty = 0, 0.0, False

    def open(self, folder: Path) -> None:
        from camr_engine.memory import JOIN, ROOM_TOKENS
        from camr_engine.rooms import Rooms

        self.close()
        self.folder = _fresh(folder)
        self.reader = self._reader or self.loader.reader(self.repo)
        self.embedder = self._embedder or self.loader.embedder()
        if self._counter is None:
            from camr_engine.bench.haul.tokens import counter

            self._counter = counter()  # the 1.7B's tokens, as the engine's rooms count them
        self.count = self._counter
        self.rooms = Rooms(self.folder / "rooms", 1, ROOM_TOKENS, JOIN)  # one byte per token: the files only count
        self.moments, self.saves_s, self._dirty = 0, 0.0, False
        self.days.reset()

    def tell(self, text: str, day: int) -> None:
        moment = self.days.moment(text, day)
        if moment is None:
            return
        vec = self.embedder.encode_one(moment)
        n = self.count(moment + "\n")
        self.rooms.add(moment, day, vec, b"x" * n, self.rooms.place(vec, n))
        self.moments += 1
        self._dirty = True

    def chosen(self, question: str) -> list[int]:
        """The room holding the moment closest to the question, then the closest moments, as the engine picks them."""
        import numpy as np

        from camr_engine.memory import CLOSEST

        r = self.rooms
        if not r.moments:
            return []
        order = np.argsort(-(r.vectors @ self.embedder.encode_one(question, is_query=True)))
        room = r.rooms[r.moments[int(order[0])].room]
        return list(room.members) + sorted(int(m) for m in order[:CLOSEST])

    def system(self, notes: str, family: str | None) -> str:
        """The engine's prompt, with the notes as words."""
        then = hint(family)
        return (f"{self.intro}\n\nNotes:\n{notes}End of notes.\nToday is {today_text(self.days.now())}."
                + (f"\n\n{then}" if then else ""))

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        if self._dirty:  # the index is saved before a question, as the engine's is
            t = time.perf_counter()
            self.rooms.save()
            self.saves_s += time.perf_counter() - t
            self._dirty = False
        t = time.perf_counter()
        picked = self.chosen(question)
        retrieval = time.perf_counter() - t
        notes = "".join(self.rooms.moments[m].text + "\n" for m in picked)
        ids = self.reader.chat_ids(self.system(notes, family), question)
        before = time.perf_counter() - t
        peak_reset()
        reply = self.reader.generate(ids, max_tokens=max_tokens)
        total = time.perf_counter() - t
        ttft = round(before + reply.ttft_s, 4)
        m = metrics(ttft_s=ttft, total_s=round(total, 4),
                    prefill_tps=round(len(ids) / reply.ttft_s, 1) if reply.ttft_s > 0 else None,
                    decode_tps=decode_tps(reply.gen_tokens, total, before + reply.ttft_s),
                    retrieval_ms=round(retrieval * 1000, 3), bytes_read=0, gbps=None, read_share=0.0,
                    context_tokens=len(ids), history_tokens=sum(r.tokens for r in self.rooms.rooms),
                    peak_ram_gb=peak_gb(), disk_gb=round(folder_bytes(self.folder) / 1e9, 6), tier="vault")
        return Answer(reply.text, m, {"moments_read": len(picked), "answer_tokens": reply.gen_tokens,
                                      "mlx_decode_tps": round(reply.gen_tps, 1),
                                      **view(prefill=len(ids), notes=0, words=len(self.reader.tok.encode(notes)))})

    def reading_s(self) -> float:
        return self.saves_s

    def status(self) -> dict:
        if self.rooms is None:
            return {}
        return {"moments": len(self.rooms.moments), "rooms": len(self.rooms.rooms),
                "history_tokens": sum(r.tokens for r in self.rooms.rooms),
                "disk_gb": round(folder_bytes(self.folder) / 1e9, 6), "saves_s": round(self.saves_s, 3)}

    def describe(self) -> dict:
        from camr_engine.memory import CLOSEST, JOIN, ROOM_TOKENS

        return {"name": self.name, "kind": "words", "model": self.model, "repo": self.repo, "embedder": EMBEDDER,
                "room_tokens": ROOM_TOKENS, "join": JOIN, "closest": CLOSEST, "counted_in": "Qwen3-1.7B tokens",
                "moment": "[YYYY-MM-DD, day N] text" if self.days.day_numbers else "[YYYY-MM-DD] text",
                "tier": "vault (memory read as words)", "enable_thinking": THINKING, "system": self.intro,
                "prompt": NOTES_PROMPT.replace("the core, the room", "the room"), "today_line": True,
                "hint_in": "system, after the notes and the date", "hints": HINTS,
                "disk": "the whole folder: index.json, vectors.npy and one placeholder byte a token per room"}

    def close(self) -> None:
        if self.rooms is not None:
            try:
                self.rooms.save()
                self.rooms.close()
            finally:
                self.rooms = None


class Rag(Contender):
    """rag:<model>: conventional retrieval-augmented generation over the same moments, for the comparison with the
    engine. Ingest embeds each moment and keeps its words (no notes, no rooms). A question is embedded, the ``k``
    closest moments are taken, closest first, while they fit ``budget`` tokens, and pasted in as text where the
    engine's notes go, in ``order`` ("date": oldest first, as the engine re-reads its closest moments; "score":
    closest first). The same reader, embedder, dated moments, instructions, date line, family's line and question as
    the engine; only the fixed header is already read (as any runtime keeps a prompt's unchanging start), and
    everything else is read as text, every question."""

    def __init__(self, model: str, *, loader: Loader | None = None, reader=None, embedder=None,
                 dates: Callable[[int], dt.date] | None = None, day_numbers: bool = True, intro: str = INTRO,
                 k: int = RAG_K, budget: int = RAG_TOKENS, order: str = "date", finder: str = "dense"):
        if reader is None:
            parse(f"rag:{model}")
        self.finder = finder  # "words": the engine's word finder (camr_engine.finder), so RAG gets the same search
        if order not in RAG_ORDERS:
            raise ValueError(f"order is one of {RAG_ORDERS}, not {order!r}")
        self.model, self.repo, self.name = model, MODELS.get(model), f"rag:{model}"
        self.loader, self._reader, self._embedder = loader or Loader(), reader, embedder
        self.days, self.intro, self.k, self.budget, self.order = _Days(dates, day_numbers), intro, k, budget, order
        self.reader = self.embedder = self.notebook = None
        self.folder: Path | None = None
        self.texts: list[str] = []
        self.counts: list[int] = []
        self.vectors = None
        self._pending: list = []
        self.moments, self.embed_s, self.saves_s, self._dirty = 0, 0.0, 0.0, False

    def open(self, folder: Path) -> None:
        import numpy as np

        from camr_engine.notes import Notebook

        self.close()
        self.folder = _fresh(folder)
        self.reader = self._reader or self.loader.reader(self.repo)
        self.embedder = self._embedder or self.loader.embedder()
        self.texts, self.counts, self._pending = [], [], []
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.moments, self.embed_s, self.saves_s, self._dirty = 0, 0.0, 0.0, False
        self.days.reset()
        head, _ = self.prompt(dt.date(2026, 1, 1), "?")
        self.notebook = Notebook(self.reader, head)  # the fixed header, read once and kept

    def prompt(self, today: dt.date, question: str, then: str = "") -> tuple[list[int], list[int]]:
        """The engine's prompt (camr_engine.memory.Memory.prompt, with ``intro``): the header up to the notes, and
        the part after them, as token ids."""
        system = f"{self.intro}\n\nNotes:\n{_SLOT}End of notes.\nToday is {today_text(today)}." + (
            f"\n\n{then}" if then else "")
        text = self.reader.tok.apply_chat_template([{"role": "system", "content": system},
                                                    {"role": "user", "content": question}],
                                                   add_generation_prompt=True, enable_thinking=THINKING,
                                                   tokenize=False)
        head, rest = text.split(_SLOT)
        return self.reader.tok.encode(head), self.reader.tok.encode(rest)

    def ids(self, text: str) -> list[int]:
        return self.reader.tok.encode(text + "\n")  # a moment as the engine reads it as words

    def tell(self, text: str, day: int) -> None:
        moment = self.days.moment(text, day)
        if moment is None:
            return
        t = time.perf_counter()
        self._pending.append(self.embedder.encode_one(moment))
        self.embed_s += time.perf_counter() - t
        self.texts.append(moment)
        self.counts.append(len(self.ids(moment)))
        self.moments += 1
        self._dirty = True

    def _flush(self) -> None:
        """Vectors embedded since the last question join the matrix searched."""
        import numpy as np

        if self._pending:
            new = np.stack(self._pending).astype(np.float32)
            self.vectors = new if not self.vectors.size else np.concatenate([self.vectors, new])
            self._pending = []

    def _save(self) -> None:
        """The index (each moment's words) and the vectors, beside each other in the folder."""
        import numpy as np

        self._flush()
        tmp = self.folder / "index.json.tmp"
        tmp.write_text(json.dumps({"moments": self.texts, "tokens": self.counts}))
        os.replace(tmp, self.folder / "index.json")
        np.save(self.folder / "vectors.npy", self.vectors)

    def pick(self, question: str) -> tuple[list[int], list[float]]:
        """The moments to paste in, in the order they go, and the closeness of each."""
        import numpy as np

        if not self.texts:
            return [], []
        self._flush()
        sims = self.vectors @ np.asarray(self.embedder.encode_one(question, is_query=True), dtype=np.float32)
        if self.finder == "words":
            from camr_engine.finder import LineIndex

            if getattr(self, "_lines", None) is None or self._lines.moments != len(self.texts):
                self._lines = LineIndex(self.texts)
            ranked = self._lines.order(question, sims)
        else:
            ranked = np.argsort(-sims)
        picked, total = [], 0
        for i in ranked[:self.k]:
            n = self.counts[int(i)]
            if total + n > self.budget:
                continue  # past the budget: a shorter one further down may still fit
            picked.append(int(i))
            total += n
        if self.order == "date":
            picked.sort()
        return picked, [float(sims[i]) for i in picked]

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        if self._dirty:  # the index is saved before a question, as the engine's is
            t = time.perf_counter()
            self._save()
            self.saves_s += time.perf_counter() - t
            self._dirty = False
        peak_reset()
        t = time.perf_counter()  # the wait counts the search, as the engine's counts its choosing
        picked, scores = self.pick(question)
        words = [i for m in picked for i in self.ids(self.texts[m])]
        retrieval = time.perf_counter() - t
        head, rest = self.prompt(self.days.now(), question, hint(family))
        ids = words + rest
        desk = self.notebook.desk([])  # the header alone, already read
        before = time.perf_counter() - t
        reply = self.reader.generate(ids, cache=desk, max_tokens=max_tokens)
        total = time.perf_counter() - t
        peak = peak_gb()
        ttft = round(before + reply.ttft_s, 4)
        m = metrics(ttft_s=ttft, total_s=round(total, 4),
                    prefill_tps=round(len(ids) / reply.ttft_s, 1) if reply.ttft_s > 0 else None,
                    decode_tps=decode_tps(reply.gen_tokens, total, before + reply.ttft_s),
                    retrieval_ms=round(retrieval * 1000, 3), bytes_read=0, gbps=None, read_share=0.0,
                    context_tokens=len(head) + len(ids), history_tokens=sum(self.counts), peak_ram_gb=peak,
                    disk_gb=round(folder_bytes(self.folder) / 1e9, 6) if self.folder is not None else None,
                    tier="vault")
        return Answer(reply.text, m, {"moments_read": len(picked), "scores": [round(x, 4) for x in scores],
                                      "answer_tokens": reply.gen_tokens, "mlx_decode_tps": round(reply.gen_tps, 1),
                                      **view(prefill=len(ids), notes=0, words=len(words))})

    def reading_s(self) -> float:
        return self.saves_s

    def status(self) -> dict:
        if self.folder is None:
            return {}
        return {"moments": len(self.texts), "history_tokens": sum(self.counts), "embed_s": round(self.embed_s, 3),
                "saves_s": round(self.saves_s, 3), "disk_gb": round(folder_bytes(self.folder) / 1e9, 6),
                "peak_footprint_gb": _peak_footprint_gb()}

    def describe(self) -> dict:
        return {"name": self.name, "kind": "rag", "model": self.model, "repo": self.repo, "embedder": EMBEDDER,
                "k": self.k, "budget_tokens": self.budget, "order": self.order, "finder": self.finder,
                "retrieval": "the question embedded (as a query), cosine over every moment's vector, the k closest "
                             "taken closest first while they fit the budget",
                "moment": "[YYYY-MM-DD, day N] text" if self.days.day_numbers else "[YYYY-MM-DD] text",
                "ingest": "embed only: each moment's vector and words; no notes, no rooms, no model reading",
                "tier": "vault (memory read as words)", "enable_thinking": THINKING, "system": self.intro,
                "prompt": NOTES_PROMPT.replace("the core, the room and the closest moments", "the picked moments"),
                "today_line": True, "hint_in": "system, after the notes and the date", "hints": HINTS,
                "header": "the fixed header (instructions up to \"Notes:\") read once and kept, as the engine's is",
                "disk": "the whole folder: index.json (each moment's words) and vectors.npy"}

    def close(self) -> None:
        if self.folder is not None and self._dirty:
            self._save()
            self._dirty = False
        self.notebook = None


def _mark(cache) -> list[tuple[str, Any]]:
    """Where each layer of a cache stands, so it can be put back: a length for a cache that can be cut, a copy of
    the state for one that cannot (a linear-attention layer's running state)."""
    return [("cut", c.offset) if c.is_trimmable() else ("state", _copy(c.state)) for c in cache]


def _copy(state):
    return tuple(list(x) if isinstance(x, list) else x for x in state) if isinstance(state, tuple) else state


def rewind(cache, marks: list[tuple[str, Any]]) -> None:
    """Put a cache back where ``_mark`` found it: everything a question and its answer added is dropped."""
    for c, (how, saved) in zip(cache, marks):
        if how == "cut":
            extra = c.offset - saved
            if extra > 0:
                c.trim(extra)
        else:
            c.state = _copy(saved)


class Bare(Contender):
    """bare:<model>: no memory. The most recent ``window`` tokens of the history are read once per checkpoint, and
    each question is answered after them and then cut off again."""

    def __init__(self, model: str, *, loader: Loader | None = None, reader=None, window: int | None = None,
                 intro: str | None = None):
        if reader is None:
            parse(f"bare:{model}")
        self.intro = intro  # None: the yardstick's wording; else these instructions, the window given as notes
        self.model, self.repo, self.name = model, MODELS.get(model), f"bare:{model}"
        self.window = window or WINDOWS[model]
        self.loader, self._reader = loader or Loader(), reader
        self.reader = None
        self.lines: list[str] = []
        self.counts: list[int] = []  # each line's tokens, with the blank line after it
        self.cache = self.marks = None
        self.head: list[int] = []
        self.system = ""
        self.start = 0  # the first line in the window
        self.prefill: dict = {}
        self.prefills = 0
        self.read_s = 0.0  # every window read so far
        self.sep = 1  # the blank line's tokens (one in Qwen3's vocabulary)

    def open(self, folder: Path) -> None:
        self.reader = self._reader or self.loader.reader(self.repo)
        self.lines, self.counts, self.cache, self.marks = [], [], None, None
        self.sep = len(self.reader.tok.encode(JOIN_LINES))

    def tell(self, text: str, day: int) -> None:
        self.lines.append(text)
        self.cache = None  # the window moved: read again before the next question

    def _template(self, question: str) -> str:
        return self.reader.tok.apply_chat_template([{"role": "system", "content": self.system},
                                                    {"role": "user", "content": question}],
                                                   add_generation_prompt=True, enable_thinking=THINKING,
                                                   tokenize=False)

    def read_window(self) -> None:
        """Read the most recent ``window`` tokens of the history, whole lines only, into a cache. The lines are joined
        by a blank line and the history closed after one more, as the yardstick's request has them."""
        tok = self.reader.tok
        for line in self.lines[len(self.counts):]:
            self.counts.append(len(tok.encode(line)) + self.sep)
        start, total = len(self.lines), 0
        while start > 0 and total + self.counts[start - 1] <= self.window:
            start -= 1
            total += self.counts[start]
        self.start = start
        lines = "".join(x + JOIN_LINES for x in self.lines[start:])
        self.system = (f"{BARE_SYSTEM}\n\n{OPENER}{lines}</history>" if self.intro is None else
                       f"{self.intro}\n\nNotes:\n{lines}End of notes.")
        text = self._template("?")
        self.head = tok.encode(text[:text.index(self.system) + len(self.system)])
        peak_reset()
        t = time.perf_counter()
        self.cache = self.reader.new_cache(self.head)
        seconds = time.perf_counter() - t
        self.read_s += seconds
        self.marks = _mark(self.cache)
        self.prefills += 1
        self.prefill = {"tokens": len(self.head), "seconds": round(seconds, 3),
                        "tps": round(len(self.head) / seconds, 1) if seconds > 0 else None,
                        "lines": len(self.lines) - start, "first_line": start, "peak_ram_gb": peak_gb()}

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        if self.cache is None:
            self.read_window()
        then = hint(family)
        text = self._template(question + (f"\n\n{then}" if then else ""))
        rest = self.reader.tok.encode(text[text.index(self.system) + len(self.system):])
        peak_reset()
        t = time.perf_counter()
        try:
            reply = self.reader.generate(rest, cache=self.cache, max_tokens=max_tokens)
        finally:  # the question and whatever was written of its answer go, even when generating failed
            try:
                rewind(self.cache, self.marks)
            except Exception:  # noqa: BLE001: a cache that cannot be put back is read again
                self.cache = self.marks = None
        total = time.perf_counter() - t
        m = metrics(ttft_s=round(reply.ttft_s, 4), total_s=round(total, 4),
                    prefill_tps=round(len(rest) / reply.ttft_s, 1) if reply.ttft_s > 0 else None,
                    decode_tps=decode_tps(reply.gen_tokens, total, reply.ttft_s), retrieval_ms=None, bytes_read=0,
                    gbps=None, read_share=None, context_tokens=len(self.head) + len(rest),
                    history_tokens=sum(self.counts), peak_ram_gb=peak_gb(), disk_gb=0.0, tier=None)
        return Answer(reply.text, m, {"window_tokens": len(self.head), "window_read_s": self.prefill.get("seconds"),
                                      "question_tokens": len(rest), "answer_tokens": reply.gen_tokens,
                                      "mlx_decode_tps": round(reply.gen_tps, 1),
                                      **view(prefill=len(rest), notes=len(self.head), words=0)})

    def reading_s(self) -> float:
        return self.read_s

    def status(self) -> dict:
        return {"window": self.window, "lines_told": len(self.lines), "history_tokens": sum(self.counts),
                "prefill": dict(self.prefill), "prefills": self.prefills, "peak_footprint_gb": _peak_footprint_gb()}

    def describe(self) -> dict:
        return {"name": self.name, "kind": "bare", "model": self.model, "repo": self.repo, "window": self.window,
                "system": BARE_SYSTEM if self.intro is None else self.intro,
                "opener": OPENER if self.intro is None else "Notes:\n", "lines_joined_by": JOIN_LINES,
                "prompt": "system: the instructions, the opener, the window's lines each followed by a blank line, "
                          "then </history>; user: the question, then the family's line",
                "today_line": False, "hint_in": "user, after the question", "enable_thinking": THINKING,
                "hints": HINTS,
                "cost": "the window is read once per checkpoint, counted as the checkpoint's ingest; each question "
                        "is appended and cut off again"}

    def close(self) -> None:
        self.cache = self.marks = None


def make(spec: str, loader: Loader | None = None, **kw) -> Contender:
    """The contender ``engine:<model>``, ``words:<model>``, ``bare:<model>`` or ``rag:<model>``."""
    kind, model = parse(spec)
    cls = {"engine": Engine, "words": Words, "bare": Bare, "rag": Rag}[kind]
    return cls(model, loader=loader or Loader(), **kw)


# Settings a run can give the engine's desk (``--desk``) or RAG (``--rag``), by their short names.
DESK_KEYS = {"rooms": ("desk_rooms", int), "tokens": ("desk_tokens", int), "order": ("desk_order", str),
             "closest": ("closest", int), "reread": ("reread", str), "finder": ("finder", str)}
RAG_KEYS = {"k": ("k", int), "budget": ("budget", int), "order": ("order", str), "finder": ("finder", str)}


def parse_settings(kind: str, text: str | None) -> dict:
    """``rooms=3,order=date`` for the engine's desk (kind "engine"), ``k=8,budget=1024`` for RAG (kind "rag")."""
    keys = DESK_KEYS if kind == "engine" else RAG_KEYS
    out: dict[str, Any] = {}
    for part in filter(None, (text or "").split(",")):
        k, _, v = part.partition("=")
        if k not in keys:
            raise ValueError(f"{kind} takes {', '.join(keys)}, not {k!r}")
        name, cast = keys[k]
        out[name] = cast(v)
    return out


def settings_tag(kind: str, settings: dict) -> str:
    """The settings as a name's suffix: ``[order=date,rooms=3]`` (empty when there are none)."""
    inv = {v[0]: k for k, v in (DESK_KEYS if kind == "engine" else RAG_KEYS).items()}
    tail = ",".join(f"{inv[k]}={v}" for k, v in sorted(settings.items(), key=lambda kv: inv[kv[0]]))
    return f"[{tail}]" if tail else ""


def haul_contender(spec: str, loader: Loader | None = None, *, learn: bool = False, watch: bool = False,
                   wake: bool = False, wording: str = "yardstick", bits: int | None = None,
                   disk_gb: float | None = None, desk: dict | None = None, rag: dict | None = None,
                   snapshots: Path | None = None) -> Contender:
    """A contender with the Long Haul's wording. ``wording`` "yardstick": the engine and words read LONGHAUL_INTRO,
    bare reads the yardstick's own. "own": every one reads the engine's own instructions (memory.INTRO), bare with
    its window as the notes, and the name says so ("+own"). ``learn``, ``watch`` and ``wake`` are the engine's, and
    so are ``bits``: how its rooms keep their notes on the SSD (memory.BITS when not given; the name says so,
    "+8bit"), and ``disk_gb``: its disk budget in GB instead of DISK_BYTES (the name says so, "+8GB"). ``desk`` sets
    the engine's desk (Memory's desk_rooms, desk_tokens, desk_order, closest) and ``rag`` RAG's k, budget and order;
    the name carries either (``[rooms=3]``). ``snapshots`` keeps a clone of the engine's memory at each cut."""
    kind, _ = parse(spec)
    if wording not in WORDINGS:
        raise ValueError(f"wording is one of {', '.join(WORDINGS)}, not {wording!r}")
    own = wording == "own"
    kw: dict[str, Any] = {"intro": INTRO} if own else ({} if kind == "bare" else {"intro": LONGHAUL_INTRO})
    if kind == "engine":
        kw.update(learn=learn, watch=watch, wake=wake)
        if bits is not None:
            kw["bits"] = bits
        if disk_gb is not None:
            kw["disk_bytes"] = int(disk_gb * 2**30)
        kw.update(desk or {})
        if snapshots is not None:
            kw["snapshots"] = Path(snapshots)
    if kind == "rag":
        kw.update(rag or {})
    c = make(spec, loader, **kw)
    if kind in ("engine", "rag"):
        c.name += settings_tag(kind, (desk if kind == "engine" else rag) or {})
    if kind == "engine" and bits is not None:
        c.name += f"+{bits}bit"
    if kind == "engine" and disk_gb is not None:
        c.name += f"+{disk_gb:g}GB"
    if own:
        c.name += "+own"
    return c


WORDINGS = ("yardstick", "own")


def memory_folder(task: str, name: str, memories: Path = MEMORIES) -> Path:
    return Path(memories) / f"{task}-{slug(name)}-{dt.datetime.now():%Y%m%d-%H%M%S}.nosync"


def haul_meta(folder: Path) -> dict:
    m = json.loads((Path(folder) / "manifest.json").read_text())
    return {"dir": str(folder), "seed": m.get("seed"), "version": m.get("version"), "tokens": m.get("tokens"),
            "events": m.get("events"), "script_sha": m.get("script_sha")}


def cut_tokens(name: str) -> int:
    from camr_engine.bench.longhaul import CUTS

    return CUTS[name] if name in CUTS else int(name)


def _let_go() -> None:
    """Free what a failed contender left in memory before the next one runs."""
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except ImportError:
        pass


def _failure(e: Exception, record: dict, where: str | None, stage: str) -> None:
    """Mark a record failed: where (and at which stage) the run stopped, and why."""
    record["failed"] = {"at": where, "stage": stage, "error": f"{type(e).__name__}: {e}"[:400]}
    record["finished"] = dt.datetime.now().isoformat(timespec="seconds")


# -- the two runs


def longhaul(specs: Sequence[str], folder: Path = HAUL, *, cuts: Sequence[str] | None = None, limit: int | None = None,
             memories: Path = MEMORIES, records: Path = RECORDS, loader: Loader | None = None,
             progress: Callable[[str], None] = print, learn: bool = False, watch: bool = False,
             wake: bool = False, wording: str = "yardstick", bits: int | None = None,
             disk_gb: float | None = None, desk: dict | None = None, rag: dict | None = None,
             snapshots: Path | None = None) -> list[dict]:
    """Each contender through the Long Haul's checkpoints, one after another; returns their records. A contender
    that fails is recorded with ``failed`` (its checkpoints so far kept) and the next one runs."""
    from camr_engine.bench.longhaul import CUTS, checkpoints, grader

    names = list(cuts or CUTS)
    events, cps = checkpoints(Path(folder), {n: CUTS[n] for n in names})
    loader = loader or Loader()
    out = []
    for spec in specs:
        c = haul_contender(spec, loader, learn=learn, watch=watch, wake=wake, wording=wording, bits=bits,
                           disk_gb=disk_gb, desk=desk, rag=rag, snapshots=snapshots)
        rec = run(c, events, cps, task="longhaul", grader=grader, limit=limit, records=records,
                  folder=memory_folder("longhaul", c.name, memories), progress=progress,
                  meta={"haul": haul_meta(folder), "cuts": names}, raise_failure=False)
        out.append(rec)
        if "failed" in rec:
            _let_go()
    return out


def speed_questions(probes: list[dict], tokens: int, n: int = SPEED_QUESTIONS, seed: int = 0) -> list[dict]:
    """``n`` short questions askable after the first ``tokens`` tokens, every short family in turn."""
    from camr_engine.bench.haul.sample import askable

    rng = random.Random(f"speed:{seed}:{tokens}")
    fams: dict[str, list[dict]] = {}
    for q in askable(probes, tokens):
        if q["family"] in SHORT:
            fams.setdefault(q["family"], []).append(q)
    for qs in fams.values():
        rng.shuffle(qs)
    picked: list[dict] = []
    while len(picked) < n and any(fams.values()):
        for f in SHORT:
            if fams.get(f) and len(picked) < n:
                picked.append(fams[f].pop(0))
    return [{"id": q["id"], "question": q["ask"], "expected": q["answer"], "family": q["family"], "probe": q}
            for q in picked]


def speed(contender: Contender, folder: Path = HAUL, *, memory: Path | None = None, marks: Sequence[int] = MARKS,
          questions: int = SPEED_QUESTIONS, until: int | None = None, records: Path = RECORDS,
          progress: Callable[[str], None] = print, save: bool = True, raise_failure: bool = True) -> dict:
    """Ingest the Long Haul once; at each mark of moments kept (and at the end) ask a few short questions and record
    what retrieval cost, with the ingest throughput and the disk used since the last point. Asking is not counted
    as ingest time. A failure is saved in the record (``failed``), then raised again unless ``raise_failure`` is
    false."""
    from camr_engine.bench.haul.script import load_events, load_probes

    events, probes = load_events(Path(folder)), load_probes(Path(folder))
    memory = memory or memory_folder("speed", contender.name)
    started = dt.datetime.now()
    path = record_path("speed", contender.name, started, records)
    record: dict[str, Any] = {"kind": "speed", "task": "speed", "contender": {"name": contender.name},
                              "thinking": THINKING, "marks": list(marks), "questions": questions, "until": until,
                              "folder": str(memory), "haul": haul_meta(folder),
                              "started": started.isoformat(timespec="seconds"), "environment": environment(),
                              "history_tokens": "the Long Haul's own count of the tokens told so far", "points": []}
    where: dict[str, Any] = {"at": None, "stage": "open"}
    try:
        contender.open(Path(memory))
        record["contender"] = contender.describe()
        _speed(contender, events, probes, record, path, marks, questions, until, progress, save, where)
    except Exception as e:  # noqa: BLE001: the record says where it stopped
        _failure(e, record, where["at"], where["stage"])
        if save:
            record["path"] = str(write_record(record, path))
        progress(f"{contender.name} failed at {where['at']} ({where['stage']}): {record['failed']['error']}")
        if raise_failure:
            raise
    finally:
        contender.close()
    return record


def _speed(contender: Contender, events: list[dict], probes: list[dict], record: dict, path: Path,
           marks: Sequence[int], questions: int, until: int | None, progress: Callable[[str], None], save: bool,
           where: dict) -> dict:
    """The ingest and its points, for ``speed`` (which opens and closes the contender around it)."""
    from camr_engine.bench.longhaul import grader, line

    left = sorted(marks)
    last = {"t": time.perf_counter(), "events": 0, "tokens": 0}
    ingest_s = 0.0

    def point(told: int, e: dict, end: bool = False) -> None:
        nonlocal ingest_s
        tell_s = time.perf_counter() - last["t"]
        where.update(at=f"{told} events", stage="ask")
        read0 = contender.reading_s()
        answers = ask_all(contender, speed_questions(probes, e["cum_tokens"], questions), grader,
                          history_tokens=e["cum_tokens"])
        read_s = max(contender.reading_s() - read0, 0.0)
        seg = tell_s + read_s
        ingest_s += seg
        n_events, n_tokens = told - last["events"], e["cum_tokens"] - last["tokens"]
        where["stage"] = "status"
        st = contender.status()
        p = {"moments": getattr(contender, "moments", told), "events": told, "history_tokens": e["cum_tokens"],
             "day": e["day"], "end": end,
             "ingest": {"events": n_events, "tokens": n_tokens, "seconds": round(seg, 3), "tell_s": round(tell_s, 3),
                        "read_s": round(read_s, 3),
                        "events_per_s": round(n_events / seg, 2) if seg > 0 else None,
                        "tokens_per_s": round(n_tokens / seg, 1) if seg > 0 else None,
                        "overall_events_per_s": round(told / ingest_s, 2) if ingest_s > 0 else None,
                        "overall_tokens_per_s": round(e["cum_tokens"] / ingest_s, 1) if ingest_s > 0 else None},
             "disk_gb": st.get("disk_gb"), "footprint_gb": _footprint_gb(), "status": st,
             "summary": summarize(answers)["all"], "answers": answers}
        record["points"].append(p)
        record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        if save:
            record["path"] = str(write_record(record, path))
        s = p["summary"]
        progress(f"{contender.name} {p['moments']:,} moments ({e['cum_tokens']:,} tokens): ingest "
                 f"{p['ingest']['events_per_s']} events/s, {p['ingest']['tokens_per_s']} tokens/s; retrieval p50 "
                 f"{s['retrieval_ms']['p50']} ms, read {s['bytes_read']['p50']} B at {s['gbps']['p50']} GB/s, first "
                 f"word p50 {s['ttft_s']['p50']} s; disk {p['disk_gb']} GB")
        last.update(t=time.perf_counter(), events=told, tokens=e["cum_tokens"])

    told = 0
    for e in events:
        if until is not None and e["cum_tokens"] > until:
            break
        where.update(at=f"{told} events", stage="tell")
        contender.tell(line(e), e["day"])
        told += 1
        n = getattr(contender, "moments", told)
        if left and n >= left[0]:
            while left and n >= left[0]:
                left.pop(0)
            point(told, e)
    if told and last["events"] != told:
        point(told, events[told - 1], end=True)
    elif record["points"]:
        record["points"][-1]["end"] = True
    record["not_reached"] = left
    if save:
        record["path"] = str(write_record(record, path))
    return record


# -- the command line


def parser() -> argparse.ArgumentParser:
    from camr_engine.bench.longhaul import CUTS

    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.local")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("longhaul", help="local contenders through the Long Haul's checkpoints")
    h.add_argument("--contender", action="append", required=True,
                   help="engine:<model>, words:<model> or bare:<model>; give it again for another")
    h.add_argument("--dir", type=Path, default=HAUL, help="a built Long Haul")
    h.add_argument("--cuts", nargs="+", choices=list(CUTS), help="some of the cuts (default: all)")
    h.add_argument("--limit", type=int, help="at most N questions per checkpoint, every family in turn")
    h.add_argument("--memories", type=Path, default=MEMORIES)
    h.add_argument("--records", type=Path, default=RECORDS)
    h.add_argument("--snapshots", type=Path, help="keep an APFS clone of the engine's memory at each cut here")
    s = sub.add_parser("speed", help="retrieval and first-word time as the memory grows, during one ingest")
    s.add_argument("--contender", action="append", required=True)
    s.add_argument("--dir", type=Path, default=HAUL)
    s.add_argument("--marks", nargs="+", type=int, default=list(MARKS), help="moments at which to take a point")
    s.add_argument("--questions", type=int, default=SPEED_QUESTIONS, help="short questions asked at each point")
    s.add_argument("--until", help="stop the ingest at a cut (64K, 256K, 1M, 2M) or a token count")
    s.add_argument("--memories", type=Path, default=MEMORIES)
    s.add_argument("--records", type=Path, default=RECORDS)
    for p in (h, s):
        p.add_argument("--learn", action="store_true",
                       help="let the engine's questions change its memory, as in the app (off: read-only)")
        p.add_argument("--watch", action="store_true",
                       help="watch the engine's attention while it answers (its peak RAM is then not reported)")
        p.add_argument("--wording", choices=("yardstick", "own"), default="yardstick",
                       help="yardstick: Claude's instructions for everyone (the default); own: the engine's own "
                            "instructions (memory.INTRO) for every local contender")
        p.add_argument("--bits", type=int, choices=(16, 8, 4),
                       help="how the engine's new rooms keep their notes on the SSD (default: memory.BITS)")
        p.add_argument("--disk-gb", type=float,
                       help="the engine's disk budget for awake room files, in GB (default: 40 GB)")
        p.add_argument("--desk", help="the engine's desk: rooms=N,tokens=N,order=date|best_last,closest=N")
        p.add_argument("--rag", help="RAG's retrieval: k=N,budget=N,order=date|score")
        p.add_argument("--wake", action="store_true",
                       help="wake an asleep room the engine asks (its notes written again from its words) instead of "
                            "reading it as words")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    a = parser().parse_args(argv)
    for spec in a.contender:
        parse(spec)  # every name checked before any model is loaded
    if a.cmd == "longhaul":
        for r in longhaul(a.contender, a.dir, cuts=a.cuts, limit=a.limit, memories=a.memories, records=a.records,
                          learn=a.learn, watch=a.watch, wake=a.wake, wording=a.wording, bits=a.bits,
                          disk_gb=a.disk_gb, desk=parse_settings("engine", a.desk), rag=parse_settings("rag", a.rag),
                          snapshots=a.snapshots):
            print(r.get("path"))
        return 0
    loader = Loader()
    for spec in a.contender:
        c = haul_contender(spec, loader, learn=a.learn, watch=a.watch, wake=a.wake, wording=a.wording, bits=a.bits,
                           disk_gb=a.disk_gb, desk=parse_settings("engine", a.desk), rag=parse_settings("rag", a.rag))
        r = speed(c, a.dir, memory=memory_folder("speed", c.name, a.memories), marks=a.marks, questions=a.questions,
                  until=cut_tokens(a.until) if a.until else None, records=a.records, raise_failure=False)
        if "failed" in r:
            _let_go()
        print(r.get("path"))
    return 0


__all__ = ["RAG_K", "RAG_TOKENS", "Rag", "parse_settings", "settings_tag", "view", "BARE_SYSTEM", "DISK_BYTES", "HINTS", "LONGHAUL_INTRO", "MARKS", "METRICS", "MODELS", "RAM_BYTES", "WINDOWS",
           "Bare", "Engine", "Loader", "Words", "haul_contender", "kv_shape", "longhaul", "make", "max_tokens", "parse",
           "rewind", "speed", "speed_questions"]


if __name__ == "__main__":
    from camr_engine.app.measuring import measuring

    with measuring("local"):  # the app pauses its views and loads nothing while this measures
        raise SystemExit(main())
