"""The Long Haul from the command line.

  python -m camr_engine.bench.haul build --seed 1 --out records/bench/haul-seed1
  python -m camr_engine.bench.haul sample --n 15 --per-family --cut 1M --dir records/bench/haul-seed1
  python -m camr_engine.bench.haul grade --dir records/bench/haul-seed1 --answers answers.jsonl --cut 1M

``sample`` prints one probe per line (as asked at that cut, with its answer at that point). Without ``--dir`` it
builds the script for ``--seed`` in memory first. ``grade`` reads lines of {"id": ..., "answer": ...}; a line it
cannot read, an unknown id or a probe not askable at the cut gets verdict null and the run goes on.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from camr_engine.bench.haul.grade import grade
from camr_engine.bench.haul.sample import at_cut, sample
from camr_engine.bench.haul.script import CUTS, build, load_probes, write


def _cut(name: str) -> int:
    if name in CUTS:
        return CUTS[name]
    return int(name)


def _probes(a: argparse.Namespace) -> list[dict]:
    if a.dir:
        return load_probes(Path(a.dir))
    return build(a.seed).probes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.haul")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write script.jsonl, probes.jsonl and manifest.json")
    b.add_argument("--seed", type=int, default=1)
    b.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("sample", help="a stratified sample of the probes askable at a cut")
    s.add_argument("--n", type=int, default=15)
    s.add_argument("--per-family", action="store_true", help="n from each family, not n in all")
    s.add_argument("--cut", default="2M", help=f"one of {', '.join(CUTS)}, or a token count")
    s.add_argument("--dir", help="a built Long Haul (default: build --seed in memory)")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--sample-seed", type=int, default=0)
    s.add_argument("--out", type=Path, help="write the sample here instead of printing it")
    g = sub.add_parser("grade", help="grade answers given as JSON lines of {id, answer}")
    g.add_argument("--answers", type=Path, required=True)
    g.add_argument("--cut", default="2M")
    g.add_argument("--dir")
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--browser", action="store_true", help="also load page answers in a headless browser")
    a = ap.parse_args(argv)

    if a.cmd == "build":
        haul = build(a.seed)
        write(haul, a.out)
        m = haul.manifest
        print(f"{m['events']} events, {m['tokens']:,} tokens over {m['days']} days -> {a.out}")
        for name, c in m["cuts"].items():
            print(f"  {name:>4}: {c['tokens']:>9,} tokens to day {c['last_day']:>3}, "
                  f"{sum(c['probes'].values())} probes askable")
        return 0

    if a.cmd == "sample":
        picked = sample(_probes(a), _cut(a.cut), a.n, per_family=a.per_family, seed=a.sample_seed)
        lines = [json.dumps(p, ensure_ascii=False) for p in picked]
        if a.out:
            a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"{len(picked)} probes -> {a.out}", file=sys.stderr)
        else:
            print("\n".join(lines))
        return 0

    by_id = {p["id"]: p for p in _probes(a)}
    cut = _cut(a.cut)
    tally: Counter = Counter()
    for n, line in enumerate(open(a.answers, encoding="utf-8"), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            pid, answer = row["id"], row["answer"]
        except (ValueError, KeyError, TypeError):
            print(json.dumps({"id": None, "line": n, "verdict": None, "reason": "not a JSON line of {id, answer}"}))
            tally[("?", "unreadable")] += 1
            continue
        if pid not in by_id:
            print(json.dumps({"id": pid, "verdict": None, "reason": "unknown probe id"}))
            tally[("?", "unknown id")] += 1
            continue
        probe = at_cut(by_id[pid], cut)
        if probe is None:
            print(json.dumps({"id": pid, "verdict": None, "reason": "not askable at this cut"}))
            continue
        verdict, reason = grade(probe, str(answer), browser=a.browser)
        tally[(probe["family"], verdict)] += 1
        print(json.dumps({"id": pid, "family": probe["family"], "verdict": verdict, "reason": reason}))
    for (fam, verdict), n in sorted(tally.items()):
        print(f"{fam:>10} {verdict:<12} {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
