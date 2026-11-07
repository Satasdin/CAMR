"""Shelves: memory split by the kind of work it holds, so one engine keeps a project's history, code, research and
personal life apart and still answers from any of them.

Each shelf is a reach of its own (camr_engine.reach), so it has its own folder, notes and vault. The Projects shelf
is the global reach, which every session reads. A question reads every shelf, and the closest note wins, as a session
always chooses. A moment goes on the shelf it is told to go on, or ``Sorter`` puts it on the shelf whose description
it is closest to (the embedder's own measure, the one recall uses), so "Auto" files it by meaning.

The shelves are the user's: the four below are only where a new memory starts. ``add``, ``rename``, ``empty`` and
``remove`` change them, and ``shelves.json`` beside the reaches keeps the list. Emptying or removing a shelf moves its
folder to ``removed/`` beside them, so nothing is destroyed and it can be put back by hand.

``warm`` touches what a model will read first: one short answer so its kernels are built and its weights are in
memory, then the newest notes of every shelf read off the SSD, so the operating system keeps them in RAM and the
first questions fetch them at memory speed. Then it holds each shelf's disk budget (``disk_budget``, 8 GB a reach
unless ``CAMR_SHELF_DISK_GB`` says otherwise): the weakest, least recently used rooms beyond it go to sleep, their
notes deleted and their moments kept as words, so a shelf stops growing on the SSD without limit. That runs on the
session's own thread before any question; after it, each moment kept holds the budget as it is written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from camr_engine.rooms import room_id


@dataclass(frozen=True)
class Shelf:
    name: str
    label: str
    reach: str  # the reach that holds it
    about: str  # what belongs on it, as the sorter reads it
    like: tuple[str, ...] = ()  # a few moments that belong on it: the sorter's target is their mean with ``about``
    called: bool = False  # curated knowledge: read only when it is called for, never filed onto by the sorter


DEFAULTS = (
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
SHELVES: list[Shelf] = list(DEFAULTS)  # the shelves now, changed in place, so every importer sees the same list
BY_NAME: dict[str, Shelf] = {s.name: s for s in SHELVES}
MAX_LABEL = 30
WARM_BYTES = 1_500_000_000  # notes read ahead across all shelves when a model loads
WARM_CHUNK = 8 << 20
DISK_GB = 8.0  # each reach's awake notes on the SSD, at most (asleep rooms are read as words)


def disk_budget() -> int:
    """Each reach's disk budget in bytes: ``CAMR_SHELF_DISK_GB`` when set (a number of GB), else 8 GB."""
    try:
        gb = float(os.environ.get("CAMR_SHELF_DISK_GB", DISK_GB))
    except ValueError:
        gb = DISK_GB
    return int(gb * 2**30)


def _set(shelves: Iterable[Shelf]) -> None:
    SHELVES[:] = list(shelves)
    BY_NAME.clear()
    BY_NAME.update({s.name: s for s in SHELVES})


def _file(root: Path) -> Path:
    return Path(root) / "shelves.json"


def load(root: Path) -> list[Shelf]:
    """The shelves of the memory at ``root``: its own list, or the four it starts with."""
    try:
        rows = json.loads(_file(root).read_text())
        _set(Shelf(r["name"], r["label"], r["reach"], r.get("about", ""), tuple(r.get("like", ())),
                   bool(r.get("called"))) for r in rows)
    except (OSError, ValueError, KeyError, TypeError):
        _set(DEFAULTS)
    return list(SHELVES)


def _save(root: Path) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    rows = [{"name": s.name, "label": s.label, "reach": s.reach, "about": s.about, "like": list(s.like),
             "called": s.called} for s in SHELVES]
    tmp = _file(root).with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, indent=1))
    tmp.replace(_file(root))


def _label(text: str) -> str:
    label = " ".join(str(text).split())
    if not label or len(label) > MAX_LABEL:
        raise ValueError(f"a shelf's name is 1 to {MAX_LABEL} characters")
    return label


def add(root: Path, label: str, about: str = "") -> Shelf:
    """A new shelf of the user's own, in a reach of its own. ``about`` says what belongs on it, for the sorter."""
    label = _label(label)
    if any(s.label.lower() == label.lower() for s in SHELVES):
        raise ValueError(f"there is already a shelf called {label}")
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:16] or "shelf"
    name, n = base, 1
    while name in BY_NAME or name == "auto":
        n += 1
        name = f"{base}-{n}"
    shelf = Shelf(name, label, f"project:{name}", " ".join(str(about).split()) or label)
    _set([*SHELVES, shelf])
    _save(root)
    return shelf


def rename(root: Path, name: str, label: str) -> Shelf:
    label = _label(label)
    if name not in BY_NAME:
        raise KeyError(name)
    if any(s.label.lower() == label.lower() and s.name != name for s in SHELVES):
        raise ValueError(f"there is already a shelf called {label}")
    old = BY_NAME[name]
    new = Shelf(old.name, label, old.reach, old.about, old.like, old.called)
    _set(new if s.name == name else s for s in SHELVES)
    _save(root)
    return new


def _put_away(root: Path, shelf: Shelf) -> str | None:
    """Move a shelf's folder to ``removed/``. Where it went, or None when it held nothing yet."""
    from camr_engine.reach import Reach

    folder = Reach.parse(shelf.reach).path(Path(root))
    if not folder.exists():
        return None
    dest = Path(root) / "removed" / f"{shelf.name}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shelf.reach == "global":  # the global folder also holds nothing else, but it is reopened at once: move its parts
        dest.mkdir(parents=True, exist_ok=True)
        for part in folder.iterdir():
            shutil.move(str(part), str(dest / part.name))
    else:
        shutil.move(str(folder), str(dest))
    return str(dest)


def empty(root: Path, name: str) -> str | None:
    """Take everything off a shelf and keep the shelf. The session must be closed. Where the old notes went."""
    if name not in BY_NAME:
        raise KeyError(name)
    return _put_away(root, BY_NAME[name])


def remove(root: Path, name: str) -> str | None:
    """Remove a shelf and put its notes away. The session must be closed. One shelf always stays, so a remembered
    moment has somewhere to go."""
    if name not in BY_NAME:
        raise KeyError(name)
    if len(SHELVES) == 1:
        raise ValueError("keep at least one shelf")
    went = _put_away(root, BY_NAME[name])
    _set(s for s in SHELVES if s.name != name)
    _save(root)
    return went


CURATED = Path(__file__).resolve().parent / "curated"  # the shelves shipped with the engine: rules and corrections


def curated() -> list[dict]:
    """The curated shelves: {name, label, about, notes}, each note one RULE or CORRECTION line of its file."""
    out = []
    for f in sorted(CURATED.glob("*.md")):
        text = f.read_text(errors="replace")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        meta = {}
        for line in (m.group(1).splitlines() if m else []):
            k, sep, v = line.partition(":")
            if sep:
                meta[k.strip()] = v.strip()
        notes = [x.strip() for x in text[m.end() if m else 0:].splitlines() if x.startswith(("RULE ", "CORRECTION "))]
        out.append({"name": meta.get("name", f.stem), "label": meta.get("label", f.stem.title()),
                    "about": meta.get("about", ""), "notes": notes})
    return out


def add_curated(root: Path, name: str) -> tuple[Shelf, list[str]]:
    """Put a curated shelf in the list (once), as a called shelf in a reach of its own: (the shelf, its notes)."""
    got = next((c for c in curated() if c["name"] == name), None)
    if got is None:
        raise KeyError(name)
    sname = f"curated-{name}"[:20]
    if sname in BY_NAME:
        return BY_NAME[sname], got["notes"]
    label = got["label"]
    if any(s.label.lower() == label.lower() for s in SHELVES):
        label = f"{label} guide"[:MAX_LABEL]
    shelf = Shelf(sname, label, f"project:{sname}", got["about"] or label, called=True)
    _set([*SHELVES, shelf])
    _save(root)
    return shelf, got["notes"]


def shelf_of(reach: str | None) -> Shelf | None:
    """The shelf a reach label holds (None for a reach that is not a shelf, as a session's own)."""
    return next((s for s in SHELVES if s.reach == reach), None)


def reaches() -> list[str]:
    return [s.reach for s in SHELVES]


class Sorter:
    """Which shelf a moment belongs on: the shelf whose description is closest to it by the embedder."""

    def __init__(self, embedder, shelves: Iterable[Shelf] = SHELVES):
        self.shelves = [s for s in shelves if not s.called] or list(shelves)
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
        best = max(got, key=got.get)
        return next(s for s in self.shelves if s.name == best)


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
            report("warm", shelf=shelf_of(label).name, reach=label, room=room_id(f), bytes=size)
        total += used
    s = time.perf_counter() - t
    out = {"bytes": total, "files": files, "s": round(s, 3), "gbps": round(total / s / 1e9, 2) if s > 0 else None}
    report("warmed", **out)
    hold(memories, report)
    return out


def hold(memories: dict, report: Callable[..., object] | None = None) -> dict:
    """Hold every memory's disk budget (``memories``: reach label -> Memory; one without tiers or a budget is left as
    it is): its weakest, least recently used rooms beyond the budget go to sleep. Returns the rooms put to sleep, by
    reach."""
    report = report or (lambda *a, **k: None)
    out = {}
    for label, m in memories.items():
        tiers = getattr(m, "tiers", None)
        if tiers is None or tiers.disk_budget is None:
            continue
        t = time.perf_counter()
        slept = tiers.enforce()
        if slept:
            m.save()
            out[label] = slept
            report("budget", reach=label, slept=len(slept), awake_bytes=tiers.disk_bytes(),
                   budget_bytes=tiers.disk_budget, s=round(time.perf_counter() - t, 3))
    return out
