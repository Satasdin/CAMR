"""Which reach works best: the same Long Haul told into memories that reach differently, then asked from one session.

Four set-ups, the same engine and the same questions:

- ``session``: each working week is its own chat session with its own memory. The questions come in the last
  week's session, so they can reach only that week.
- ``project``: every week's session writes to one project memory, and the questions read it.
- ``global``: one memory for everything. A second project (the Long Haul built from another seed, with its own
  people, prices and settings) is told into it day by day beside this one.
- ``project+global``: this project in its own memory and the other project in the global one; the questions read
  both, as the app's sessions read their own reach and the global one.

Each reach is its own memory folder, as ``reach.Session`` lays them out. A question is asked as ``Session.answer``
asks it: embedded once, the closest room over every reach it reads, that memory's closest moments as words.
Questions are read-only, as in the Long Haul. The disk budget is large enough that no room sleeps, so sleep plays
no part in the comparison.

    python -m camr_engine.bench.reach_run --model qwen3-4b --dir ../work/haul/s1 --other ../work/haul/s2 --cut 256K
"""

from __future__ import annotations

import argparse
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Sequence

from camr_engine.bench.contender import RECORDS, Answer, run
from camr_engine.bench.local import (LONGHAUL_INTRO, MEMORIES, Engine, Loader, _Days, _fresh, _Memory, _let_go, haul_meta,
                                hint, memory_folder, peak_gb, peak_reset)
from camr_engine.reach import Reach
from camr_engine.swap import Pool, Tiers

SETUPS = {  # what each week writes to, what the questions read, and whether the other project is told
    "session": {"writes": "session", "reads": ["session:last"], "other": False},
    "project": {"writes": "project", "reads": ["project"], "other": False},
    "global": {"writes": "global", "reads": ["global"], "other": True},
    "project+global": {"writes": "project", "reads": ["project", "global"], "other": True},
}
WEEK_DAYS = 5  # working days in one chat session
DISK_BYTES = 200 * 10**9  # every reach's room files, kept awake: no room sleeps at these sizes
PROJECT, OTHER = "longhaul", "other"


class Reaches(Engine):
    """engine:<model>@<setup>: the engine with its memory split by reach (see the module's docstring)."""

    def __init__(self, model: str, setup: str, *, other: Sequence[tuple[int, str]] = (), disk_bytes: int = DISK_BYTES,
                 **kw: Any):
        if setup not in SETUPS:
            raise ValueError(f"a set-up is one of {', '.join(SETUPS)}, not {setup!r}")
        kw.setdefault("intro", LONGHAUL_INTRO)
        super().__init__(model, disk_bytes=disk_bytes, nap_days=None, **kw)
        self.setup, self.plan = setup, SETUPS[setup]
        self.name = f"engine:{model}@{setup}"
        self.other = list(other) if self.plan["other"] else []
        self.memories: dict[str, _Memory] = {}
        self.root: Path | None = None
        self.pool: Pool | None = None
        self.last_session: str | None = None
        self._told_other = 0
        self._other_days = _Days(None, True)
        self._dirty_reaches: set[str] = set()

    def open(self, folder: Path) -> None:
        self.close()
        self.root = _fresh(folder)
        self.reader_ = self._reader or self.loader.reader(self.repo)
        self.embedder_ = self._embedder or self.loader.embedder()
        self._reset()
        self.pool = Pool(self.ram_bytes)  # one RAM budget for every reach, as a Session's
        self.memories, self.last_session, self._told_other = {}, None, 0
        self._other_days.reset()
        self._dirty_reaches = set()

    def _reach(self, label: str) -> Reach:
        return Reach.parse(label) if ":" in label else Reach(label)

    def _memory(self, label: str) -> _Memory:
        if label not in self.memories:
            r = self._reach(label)
            self.memories[label] = _Memory(
                self.reader_, self.embedder_, r.path(self.root), intro=self.intro, reach=r.label, vault=True,
                core=False, tiers=Tiers(ram_bytes=self.ram_bytes, disk_bytes=self.disk_bytes, wake=self.wake,
                                        pool=self.pool), metrics=True, log=False, **self.settings)
        return self.memories[label]

    def _writes(self, day: int, project: str = PROJECT) -> str:
        kind = self.plan["writes"]
        if kind == "session":
            return f"session:w{(day - 1) // WEEK_DAYS + 1:02d}"
        return "global" if kind == "global" else f"project:{project}"

    def _keep(self, label: str, moment: str, day: int, date) -> None:
        t = time.perf_counter()
        self._memory(label).remember(moment, day, date=date)
        self.remember_s += time.perf_counter() - t
        self.moments += 1
        self._dirty_reaches.add(label)

    def tell(self, text: str, day: int) -> None:
        while self._told_other < len(self.other) and self.other[self._told_other][0] <= day:
            oday, otext = self.other[self._told_other]
            self._told_other += 1
            moment = self._other_days.moment(otext, oday)
            if moment is not None:
                self._keep("global", moment, oday, self._other_days.today)
        moment = self.days.moment(text, day)
        if moment is None:
            return
        label = self._writes(day)
        if label.startswith("session:"):
            self.last_session = label
        self._keep(label, moment, day, self.days.today)

    def reads(self) -> list[_Memory]:
        labels = [self.last_session if r == "session:last" else (f"project:{PROJECT}" if r == "project" else r)
                  for r in self.plan["reads"]]
        return [self.memories[x] for x in labels if x in self.memories]

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        for label in sorted(self._dirty_reaches):  # every index is saved before a question, never during one
            t = time.perf_counter()
            self.memories[label].save()
            self.saves_s += time.perf_counter() - t
        self._dirty_reaches = set()
        today, day = self.days.now(), self.days.day
        reads = self.reads()
        peak_reset()
        kept = [(m.tiers, dict(m.tiers.used), m.tiers.tick) for m in reads]
        hot, sizes = OrderedDict(self.pool.hot), dict(self.pool.sizes)
        try:
            t = time.perf_counter()  # as reach.Session.answer: the wait counts the choosing
            vec = self.embedder_.encode_one(question, is_query=True)
            best = None
            for m in reads:
                rec = m.choose(question, vec=vec)
                if rec.score is not None and (best is None or rec.score > best[1].score):
                    best = (m, rec)
            if best is None:  # nothing kept yet in any reach read: the plain desk of the first
                m = reads[0] if reads else self._memory(self._writes(day or 1))
                best = (m, m.choose(question, vec=vec))
            m, rec = best
            rec.seconds["choose"] = time.perf_counter() - t
            reply = m.answer(question, today, then=hint(family), max_tokens=max_tokens, chosen=rec, started=t,
                             day=day, record=True, among=reads, family=family)
        finally:  # read-only, as the Long Haul asks: recency and the hot rooms put back
            for tiers, used, tick in kept:
                tiers.used, tiers.tick = used, tick
            self.pool.hot, self.pool.sizes = hot, sizes
            self.pool.fit()
        a = self._answer(rec, reply, peak_gb())
        a.extra["reach"] = rec.reach
        return a

    def status(self) -> dict:
        per = {}
        for label, m in self.memories.items():
            st = m.state()
            per[label] = {"moments": st["moments"], "rooms": st["rooms"], "history_tokens": st["history_tokens"],
                          "disk_gb": round(st["folder_bytes"] / 1e9, 6)}
        return {"reaches": per, "moments": sum(x["moments"] for x in per.values()),
                "read": [m.reach for m in self.reads()], "remember_s": round(self.remember_s, 3),
                "saves_s": round(self.saves_s, 3)}

    def describe(self) -> dict:
        d = super().describe()
        d.update(name=self.name, setup=self.setup, plan=self.plan, week_days=WEEK_DAYS,
                 reach=f"writes {self.plan['writes']}, reads {' and '.join(self.plan['reads'])}",
                 drives="one camr_engine.memory.Memory per reach folder (reach.Session's layout), one RAM pool; a "
                        "question is chosen over the reaches read, as reach.Session.choose, then answered by that "
                        "memory with record=True and among=the reaches read",
                 other_project=bool(self.plan["other"]), other_events=len(self.other), core="off", nap_days=None)
        return d

    def close(self) -> None:
        mems, self.memories = list(self.memories.values()), {}
        for m in mems:
            m.close()
        self.memory = None


def other_lines(folder: Path, tokens: int) -> list[tuple[int, str]]:
    """The other project's events up to ``tokens``, as (day, line)."""
    from camr_engine.bench.haul.script import load_events
    from camr_engine.bench.longhaul import line

    return [(e["day"], line(e)) for e in load_events(Path(folder)) if e["cum_tokens"] <= tokens]


def main(argv: Sequence[str] | None = None) -> int:
    from camr_engine.bench.longhaul import CUTS, checkpoints, grader

    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.reach_run")
    ap.add_argument("--model", default="qwen3-4b")
    ap.add_argument("--setups", nargs="+", choices=list(SETUPS), default=list(SETUPS))
    ap.add_argument("--dir", type=Path, required=True, help="the Long Haul asked about")
    ap.add_argument("--other", type=Path, required=True, help="another Long Haul (another seed): the other project")
    ap.add_argument("--cut", choices=list(CUTS), default="256K")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--memories", type=Path, default=MEMORIES)
    ap.add_argument("--records", type=Path, default=RECORDS)
    a = ap.parse_args(argv)
    events, cps = checkpoints(a.dir, {a.cut: CUTS[a.cut]})
    other = other_lines(a.other, cps[0]["tokens"])
    loader = Loader()
    for setup in a.setups:
        c = Reaches(a.model, setup, other=other, loader=loader)
        rec = run(c, events, cps, task="reach", grader=grader, limit=a.limit, records=a.records,
                  folder=memory_folder("reach", c.name, a.memories), progress=print,
                  meta={"haul": haul_meta(a.dir), "other": haul_meta(a.other), "cuts": [a.cut], "setup": setup},
                  raise_failure=False)
        print(rec.get("path"))
        if "failed" in rec:
            _let_go()
    return 0


if __name__ == "__main__":
    from camr_engine.app.measuring import measuring

    with measuring("reach_run"):  # the app pauses its views and loads nothing while this measures
        raise SystemExit(main())
