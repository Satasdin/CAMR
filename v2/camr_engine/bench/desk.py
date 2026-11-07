"""Ways of reading one saved memory, compared on the same questions: the engine's desk set several ways, and
conventional RAG over the same moments.

A Long Haul memory is told once (``local longhaul --snapshots``, or ``scripts/dev_ingest.py`` for development
seeds) and kept as an APFS clone at each cut. Every way of reading it here answers the same questions from that one
memory, read-only, so the only thing that differs between two records is how the memory was laid in front of the
model:

- ``camr`` with desk settings: ``rooms`` (rooms laid as notes; the room of the closest moment, then the rooms of the
  next closest, awake ones only), ``tokens`` (at most this many tokens of notes on the desk), ``order`` (``date`` or
  ``best_last``), ``closest`` (moments re-read as words after the rooms);
- ``rag`` with ``k`` (moments), ``budget`` (tokens) and ``order`` (``date`` or ``score``): the closest moments as
  text, as camr_engine.bench.local.Rag reads them; its moments and vectors are the engine's own, which are exactly
  what a separate RAG ingest computes (the same dated words, the same embedder).

    python -m camr_engine.bench.desk --memory work/memories/dev-s2-4b/1M.nosync --haul work/haul/s2 --cut 1M \
        --variant camr --variant camr:rooms=3 --variant rag:k=8,budget=1024

Each variant's record is written like a Long Haul run's (one checkpoint), with ``shared_memory`` naming the memory it
read. Ingest time, disk and footprint belong to the run that told the memory, not to these records.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Callable, Sequence

from camr_engine.bench.contender import RECORDS, THINKING, ask_one, environment, record_path, summarize, write_record
from camr_engine.bench.local import LONGHAUL_INTRO, Engine, Loader, Rag, haul_meta, parse_settings, settings_tag


def parse_variant(spec: str) -> tuple[str, dict]:
    """``camr:rooms=3,order=date`` -> ("camr", {"desk_rooms": 3, "desk_order": "date"}); ``rag:k=8`` likewise."""
    kind, _, rest = spec.partition(":")
    if kind not in ("camr", "rag"):
        raise ValueError(f"a variant is camr[:...] or rag[:...], not {spec!r}")
    return kind, parse_settings("engine" if kind == "camr" else "rag", rest)


def variant_name(model: str, kind: str, settings: dict) -> str:
    who = "engine" if kind == "camr" else "rag"
    return f"{who}:{model}" + settings_tag(who, settings)


def snapshot_day(snap: Path) -> dict:
    """What the snapshot was told up to: {day, today, events, tokens}."""
    own = Path(snap) / "snapshot.json"
    if own.exists():
        return json.loads(own.read_text())
    name = Path(snap).name.removesuffix(".nosync")
    return json.loads((Path(snap).parent / "ingest.json").read_text())["cuts"][name]


def attach(model: str, snap: Path, *, loader: Loader | None = None, intro: str = LONGHAUL_INTRO,
           **settings) -> Engine:
    """An engine contender over a saved memory (``<snap>/project/longhaul``), told up to the snapshot's day. No disk
    budget is held while it is asked: its rooms stay awake or asleep exactly as the telling left them."""
    e = Engine(model, loader=loader or Loader(), intro=intro, disk_bytes=None, **settings)
    e.attach(Path(snap), int(snapshot_day(snap)["day"]))
    return e


def rag_over(engine: Engine, **settings) -> Rag:
    """RAG over the engine's own moments and vectors (the same dated words, embedded by the same embedder)."""
    import numpy as np

    from camr_engine.notes import Notebook

    m = engine.memory
    r = Rag(engine.model, reader=m.reader, embedder=m.embedder, intro=engine.intro, **settings)
    r.reader, r.embedder = m.reader, m.embedder
    r.texts = [x.text for x in m.rooms.moments]
    r.counts = [x.tokens for x in m.rooms.moments]
    r.vectors = np.asarray(m.rooms.vectors, dtype=np.float32)
    r.days = engine.days
    head, _ = r.prompt(dt.date(2026, 1, 1), "?")
    r.notebook = Notebook(m.reader, head)
    r.moments = len(r.texts)
    return r


def configure(engine: Engine, settings: dict) -> None:
    """Set the engine's desk for the next questions (desk_rooms, desk_tokens, desk_order, closest)."""
    from camr_engine.memory import CLOSEST, DESK_ROOMS

    m = engine.memory
    m.desk_rooms = settings.get("desk_rooms", DESK_ROOMS)
    m.desk_tokens = settings.get("desk_tokens")
    m.desk_order = settings.get("desk_order", "date")
    m.closest = settings.get("closest", CLOSEST)
    m.reread = settings.get("reread", "all")
    from camr_engine.memory import FINDER

    m.finder = settings.get("finder", FINDER)
    engine.settings = {**{k: v for k, v in engine.settings.items()
                          if k not in ("desk_rooms", "desk_tokens", "desk_order", "closest", "reread", "finder")},
                       **settings}


def compare(model: str, snap: Path, haul: Path, cut: str, variants: Sequence[str], *, per_family: int = 10,
            seed: int = 0, limit: int | None = None, records: Path = RECORDS, loader: Loader | None = None,
            progress: Callable[[str], None] = print, families: Sequence[str] | None = None) -> list[dict]:
    """Every variant answers the cut's questions from the memory in ``snap``; one record each."""
    from camr_engine.bench.longhaul import CUTS, checkpoints, grader

    _, cps = checkpoints(Path(haul), {cut: CUTS[cut]}, per_family=per_family, seed=seed)
    cp = cps[0]
    questions = [q for q in cp["questions"] if not families or q["family"] in families]
    if limit:
        questions = questions[:limit]
    told = snapshot_day(snap)
    if int(told.get("events", cp["events"])) != cp["events"]:
        raise ValueError(f"the snapshot holds {told.get('events')} events, the {cut} cut {cp['events']}")
    engine = attach(model, snap, loader=loader)
    out = []
    try:
        for spec in variants:
            kind, settings = parse_variant(spec)
            if kind == "camr":
                configure(engine, settings)
                who = engine
            else:
                who = rag_over(engine, **settings)
            name = variant_name(model, kind, settings)
            started = dt.datetime.now()
            path = record_path("desk", name, started, records)
            answers = [ask_one(who, q, grader, history_tokens=cp["tokens"]) for q in questions]
            desc = who.describe()
            desc["name"] = name
            rec = {"kind": "bench", "task": "longhaul", "variant": spec, "contender": desc, "thinking": THINKING,
                   "shared_memory": {"snapshot": str(snap), **{k: told.get(k) for k in ("day", "today", "events",
                                                                                        "tokens")}},
                   "haul": haul_meta(Path(haul)), "cuts": [cut], "per_family": per_family, "sample_seed": seed,
                   "started": started.isoformat(timespec="seconds"), "environment": environment(),
                   "checkpoints": [{"name": cut, "tokens": cp["tokens"], "events": cp["events"],
                                    "summary": summarize(answers), "answers": answers}],
                   "finished": dt.datetime.now().isoformat(timespec="seconds")}
            rec["path"] = str(write_record(rec, path))
            s = rec["checkpoints"][0]["summary"]["all"]
            progress(f"{name} {cut}: right {s['right']}/{s['graded']}, first word p50 {s['ttft_s']['p50']} s, "
                     f"context p50 {s['context_tokens']['p50']}")
            out.append(rec)
    finally:
        engine.close()
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.desk")
    ap.add_argument("--model", default="qwen3-4b")
    ap.add_argument("--memory", type=Path, required=True, help="a snapshot folder (<cut>.nosync)")
    ap.add_argument("--haul", type=Path, required=True)
    ap.add_argument("--cut", required=True)
    ap.add_argument("--variant", action="append", required=True)
    ap.add_argument("--per-family", type=int, default=10)
    ap.add_argument("--sample-seed", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--families", nargs="*")
    ap.add_argument("--records", type=Path, default=RECORDS)
    a = ap.parse_args(argv)
    for v in a.variant:
        parse_variant(v)
    for r in compare(a.model, a.memory, a.haul, a.cut, a.variant, per_family=a.per_family, seed=a.sample_seed,
                     limit=a.limit, records=a.records, families=a.families):
        print(r["path"])
    return 0


if __name__ == "__main__":
    from camr_engine.app.measuring import measuring

    with measuring("desk"):
        raise SystemExit(main())
