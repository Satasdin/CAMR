"""Shelves: memory split by the kind of work it holds, so one engine keeps a project's history, code, research and
personal life apart and still answers from any of them.

Each shelf is a reach of its own (camr_engine.reach), so it has its own folder, notes and vault. The Projects shelf
is the global reach, which every session reads. A question reads every shelf, and the closest note wins, as a session
always chooses. A moment goes on the shelf it is told to go on, or ``Sorter`` puts it on the shelf whose description
it is closest to (the embedder's own measure, the one recall uses), so "Auto" files it by meaning.

``warm`` touches what a model will read first: one short answer so its kernels are built and its weights are in
memory, then the newest notes of every shelf read off the SSD, so the operating system keeps them in RAM and the
first questions fetch them at memory speed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np


@dataclass(frozen=True)
class Shelf:
    name: str
    label: str
    reach: str  # the reach that holds it
    about: str  # what belongs on it, as the sorter reads it
    like: tuple[str, ...] = ()  # a few moments that belong on it: the sorter's target is their mean with ``about``


SHELVES = (
    Shelf("projects", "Projects", "global", "A project's running history: clients, suppliers, staff, prices, orders, "
          "deliveries, branches, rent, decisions, meetings and who said what.",
          ("The supplier raised the minimum order from next week.", "Wanjiru approved the new menu prices.",
           "The branch landlord wants the rent by the 28th.")),
    Shelf("coding", "Coding", "project:coding", "Software work: code, functions, classes, bugs, errors, tests, files, "
          "commands, libraries, APIs, refactors and fixes.",
          ("The unit test fails because of a float rounding bug in the function.",
           "Refactor the parser into a class and add a regression test.", "pip install failed with an import error.")),
    Shelf("research", "Research", "project:research", "Research and study: papers, findings, experiments, results, "
          "benchmarks, sources, citations, methods and reading notes.",
          ("The paper reports that retrieval beats long context on the benchmark.",
           "Our experiment measured accuracy at 1M tokens.", "Read the related work on KV cache reuse.")),
    Shelf("personal", "Personal", "project:personal", "Personal life: family, friends, birthdays, health, home, "
          "travel, money of one's own, plans and errands.",
          ("My sister's birthday is next week.", "Dentist appointment on Friday, then pick up the kids.",
           "Book the flight home for the holidays.")),
)
BY_NAME = {s.name: s for s in SHELVES}
WARM_BYTES = 1_500_000_000  # notes read ahead across all shelves when a model loads
WARM_CHUNK = 8 << 20


def shelf_of(reach: str | None) -> Shelf | None:
    """The shelf a reach label holds (None for a reach that is not a shelf, as a session's own)."""
    return next((s for s in SHELVES if s.reach == reach), None)


def reaches() -> list[str]:
    return [s.reach for s in SHELVES]


class Sorter:
    """Which shelf a moment belongs on: the shelf whose description is closest to it by the embedder."""

    def __init__(self, embedder, shelves: Iterable[Shelf] = SHELVES):
        self.shelves = list(shelves)
        rows = []
        for s in self.shelves:
            v = np.mean([np.asarray(embedder.encode_one(t), dtype=np.float32) for t in (s.about, *s.like)], axis=0)
            rows.append(v / (np.linalg.norm(v) or 1.0))
        self.vecs = np.stack(rows)
        self.embedder = embedder

    def scores(self, text: str) -> dict[str, float]:
        v = np.asarray(self.embedder.encode_one(text), dtype=np.float32)
        return {s.name: float(v @ w) for s, w in zip(self.shelves, self.vecs)}

    def sort(self, text: str) -> Shelf:
        got = self.scores(text)
        return BY_NAME[max(got, key=got.get)]


def warm(reader, memories: dict, *, budget: int = WARM_BYTES, report: Callable[..., object] | None = None) -> dict:
    """Make the first answers fast: build the model's kernels with a one-word answer, then read the newest notes of
    every shelf off the SSD (``memories``: reach label -> Memory), newest first, sharing ``budget`` bytes. Each step
    is reported (``report(kind, **data)``). Returns what was read and how long it took."""
    report = report or (lambda *a, **k: None)
    t = time.perf_counter()
    try:
        reader.generate(reader.chat_ids("Answer in one word.", "Ready?"), max_tokens=1)
    except Exception as e:  # noqa: BLE001 (a stand-in reader cannot answer; the notes are still read)
        report("warm_model", error=f"{type(e).__name__}: {e}"[:200])
    else:
        report("warm_model", s=round(time.perf_counter() - t, 3))
    shelves = [(label, m) for label, m in memories.items() if shelf_of(label) is not None]
    share = budget // max(1, len(shelves))
    total, files = 0, 0
    for label, m in shelves:
        used = 0
        for f in sorted(Path(m.path).glob("room-*.notes"), reverse=True):  # the newest notes first
            size = f.stat().st_size
            if used + size > share:
                break
            with open(f, "rb") as fh:
                while fh.read(WARM_CHUNK):
                    pass
            used += size
            files += 1
            report("warm", shelf=shelf_of(label).name, reach=label, room=int(f.stem.split("-")[1]), bytes=size)
        total += used
    s = time.perf_counter() - t
    out = {"bytes": total, "files": files, "s": round(s, 3), "gbps": round(total / s / 1e9, 2) if s > 0 else None}
    report("warmed", **out)
    return out
