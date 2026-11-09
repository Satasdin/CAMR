"""The thesis benchmarks' runs that camr_engine.bench.desk cannot do itself (DECISIONS.md, E-74):

  bare    the same model with no memory, reading its newest window
  window  Claude with no memory, reading as much of the history as its window holds
  ctx     Claude reading exactly what CAMR laid in front of the 4B
  soak    hours of telling and asking on one memory: does the first word or the RAM creep up?

Every cut's questions are the same ones the desk asks (one checkpoint built per cut, sample seed 0). Run from v2.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

APP = "camr:closest=6,finder=words,asleep=lines,read=lines,follow=3,hop=2"  # chat.APP_MEMORY, as the desk spells it
STOP_LEDGER = 57.71  # $48.71 spent before this run + the $9 approved for it (9 Nov)


def cps(haul: Path, cuts, per_family: int):
    from camr_engine.bench.longhaul import CUTS, checkpoints

    events, out = None, []
    for c in cuts:
        events, got = checkpoints(haul, {c: CUTS[c]}, per_family=per_family, seed=0)
        out.append(got[0])
    return events, out


def bare(a) -> int:
    from camr_engine.bench.contender import run
    from camr_engine.bench.local import Loader, haul_meta, make
    from camr_engine.bench.longhaul import grader

    events, points = cps(a.haul, a.cuts, a.per_family)
    rec = run(make(f"bare:{a.model}", Loader()), events, points, task="longhaul", grader=grader, records=a.records,
              folder=a.work, meta={"haul": haul_meta(a.haul), "cuts": a.cuts, "per_family": a.per_family,
                                   "sample_seed": 0}, raise_failure=False)
    print(rec.get("path"), "failed" if "failed" in rec else "ok")
    return 0


def spent() -> float:
    from camr_engine.bench.claude import Ledger

    return Ledger().spent()


def window(a) -> int:
    from camr_engine.bench.claude import Checkpoint, Claude
    from camr_engine.bench.longhaul import grader, line

    events, points = cps(a.haul, a.cuts, a.per_family)
    history = [line(e) for e in events]
    for p in points:
        if spent() >= STOP_LEDGER - 2.5:  # a checkpoint costs about $2
            print(f"stopping before {p['name']}: the approved money would run out")
            return 0
        rec = Claude(records=a.records).run(a.model, history, [Checkpoint(p["name"], p["events"], p["questions"])],
                                            grader=grader, task="longhaul", progress=print)
        print(rec.get("path"), f"ledger ${spent():.2f}", flush=True)
    return 0


def ctx(a) -> int:
    from tricky import split_chat

    from camr_engine.bench.claude import Claude
    from camr_engine.bench.contender import ask_one, environment
    from camr_engine.bench.desk import attach, configure, parse_variant
    from camr_engine.bench.longhaul import grader

    _, points = cps(a.haul, [a.cut], a.per_family)
    questions = points[0]["questions"]
    _, settings = parse_variant(APP)
    engine = attach("qwen3-4b", a.memory)
    configure(engine, settings)
    m = engine.memory
    seen: dict = {}
    real = m._generate

    def capture(said, todo, cache, max_tokens):
        seen["text"] = m.reader.tok.decode(list(m.notebook.header) + list(todo))
        return real(said, todo, cache, max_tokens)

    m._generate = capture
    claude = Claude()
    rows, t0, out = [], time.time(), None
    try:
        for q in questions:
            if spent() >= STOP_LEDGER - 0.1:
                out = "the approved money ran out"
                print(out, flush=True)
                break
            seen.clear()
            local = ask_one(engine, q, grader, history_tokens=points[0]["tokens"])
            system, user = split_chat(seen.get("text", ""))
            c = claude.call(a.model, [{"role": "user", "content": user}], system=system, max_tokens=4000,
                            purpose=f"thesis-ctx {a.cut}", prompt_tokens=len(seen.get("text", "")) // 3 + 50, cache=False)
            g = grader(q, c.text)
            rows.append({"id": q["id"], "family": q["family"], "question": q["question"], "expected": q["expected"],
                         "qwen": {"answer": local["answer"], "verdict": local["verdict"], "right": local["right"]},
                         "claude": {"answer": c.text, "verdict": g["verdict"], "right": g["right"], "call": c.as_dict()}})
            if len(rows) % 40 == 0:
                print(f"{a.cut} {len(rows)}/{len(questions)} ledger ${spent():.2f}", flush=True)
    finally:
        engine.close()
    a.records.mkdir(parents=True, exist_ok=True)
    path = a.records / f"{time.strftime('%Y%m%d-%H%M%S')}-ctx-{a.model}-{a.cut}.json"
    path.write_text(json.dumps({"kind": "thesis-ctx", "variant": APP, "cut": a.cut, "per_family": a.per_family,
                                "reader": a.model, "stopped": out, "seconds": round(time.time() - t0, 1),
                                "environment": environment(), "answers": rows}, indent=1))
    print(path, f"ledger ${spent():.2f}")
    return 0


def footprint_gb(pid: int) -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return round(int(out or 0) * 1024 / 1e9, 3)


def soak(a) -> int:
    from camr_engine.bench.contender import environment
    from camr_engine.bench.desk import attach, configure, parse_variant, snapshot_day
    from camr_engine.bench.longhaul import CUTS, checkpoints, grader, line

    work = Path(str(a.work) + ".nosync")
    subprocess.run(["rm", "-rf", str(work)], check=True)
    work.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-c", "-R", str(a.memory), str(work)], check=True)
    (work / "snapshot.json").write_text(json.dumps(snapshot_day(a.memory)))
    events, cp = checkpoints(a.haul, {a.cut: CUTS[a.cut]}, per_family=1000)
    told, questions = cp[0]["events"], [q for q in cp[0]["questions"] if q["family"] not in ("page", "code")]
    random.Random(4).shuffle(questions)
    _, settings = parse_variant(APP)
    engine = attach("qwen3-4b", work)
    configure(engine, settings)
    end, rows, t0, q_at = time.time() + a.minutes * 60, [], time.time(), 0
    try:
        while time.time() < end and told < len(events):
            for e in events[told:told + a.tell_each]:
                engine.tell(line(e), e["day"])
            told += a.tell_each
            q = questions[q_at % len(questions)]
            q_at += 1
            got = engine.ask(q["question"], max_tokens=200, family=q["family"])
            g = grader(q, got.text)
            m = got.metrics
            rows.append({"t_s": round(time.time() - t0, 1), "told": told, "ttft_s": m["ttft_s"], "decode_tps": m["decode_tps"],
                         "retrieval_ms": m["retrieval_ms"], "peak_ram_gb": m["peak_ram_gb"], "disk_gb": m["disk_gb"],
                         "rss_gb": footprint_gb(os.getpid()), "right": g["right"], "family": q["family"]})
            if len(rows) % 100 == 0:
                print(json.dumps(rows[-1]), flush=True)
    finally:
        engine.close()

    def part(xs, key):
        v = [x[key] for x in xs if x.get(key) is not None]
        return round(statistics.median(v), 4) if v else None

    n = len(rows) // 4
    quarters = [rows[i * n:(i + 1) * n] for i in range(4)]
    out = {"kind": "thesis-soak", "minutes": a.minutes, "questions": len(rows), "told_from": cp[0]["events"], "told_to": told,
           "quarters": [{k: part(q, k) for k in ("ttft_s", "decode_tps", "retrieval_ms", "peak_ram_gb", "rss_gb")}
                        | {"right": sum(bool(x["right"]) for x in q), "of": len(q)} for q in quarters],
           "thermal": subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True).stdout,
           "environment": environment(), "rows": rows}
    a.records.mkdir(parents=True, exist_ok=True)
    path = a.records / f"{time.strftime('%Y%m%d-%H%M%S')}-soak.json"
    path.write_text(json.dumps(out, indent=1))
    print(path, json.dumps(out["quarters"]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("bare", bare), ("window", window), ("ctx", ctx), ("soak", soak)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--haul", type=Path, required=True)
        p.add_argument("--records", type=Path, required=True)
        p.add_argument("--per-family", type=int, default=10)
    b = sub.choices["bare"]
    b.add_argument("--cuts", nargs="+", required=True)
    b.add_argument("--model", default="qwen3-4b")
    b.add_argument("--work", type=Path, required=True)
    w = sub.choices["window"]
    w.add_argument("--cuts", nargs="+", required=True)
    w.add_argument("--model", default="claude-sonnet-5-5")
    c = sub.choices["ctx"]
    c.add_argument("--memory", type=Path, required=True)
    c.add_argument("--cut", required=True)
    c.add_argument("--model", default="claude-sonnet-5-5")
    s = sub.choices["soak"]
    s.add_argument("--memory", type=Path, required=True)
    s.add_argument("--cut", required=True)
    s.add_argument("--work", type=Path, required=True)
    s.add_argument("--minutes", type=float, default=120)
    s.add_argument("--tell-each", type=int, default=20)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    from camr_engine.app.measuring import measuring

    with measuring("thesis"):
        raise SystemExit(main())
