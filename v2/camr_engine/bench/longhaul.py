"""The Long Haul end to end: the same questions at each cut for every contender, graded by rule.

A checkpoint is a cut of the script (64K, 256K, 1M, 2M tokens) and a stratified sample of the probes askable there,
``PER_FAMILY`` from each family, with each probe resolved to its right answer at that point. Every contender gets
exactly these checkpoints, so their scores compare. Claude reads the history as text, the most recent part that fits
its window, with no memory; the local contenders are run through the engine by their own runner.

    python -m camr_engine.bench.longhaul claude --model claude-haiku-5-5 --dir work/haul/s1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from camr_engine.bench.haul.grade import grade
from camr_engine.bench.haul.sample import askable, sample
from camr_engine.bench.haul.script import load_events, load_probes

CUTS = {"64K": 64_000, "256K": 256_000, "1M": 1_000_000, "2M": 2_000_000, "3M": 3_000_000, "4M": 4_000_000}
PER_FAMILY = 10
SAMPLE_SEED = 0
RIGHT = {"right", "right_abstain"}


def line(event: dict) -> str:
    """One event as the history shows it: a day line alone, everything else with who said it."""
    if event["role"] == "system":
        return event["text"]
    return f"{event['role'].capitalize()}: {event['text']}"


def checkpoints(folder: Path, cuts: dict[str, int] = CUTS, per_family: int = PER_FAMILY,
                seed: int = SAMPLE_SEED) -> tuple[list[dict], list[dict]]:
    """(events, checkpoints) for a built Long Haul. A checkpoint is {name, tokens, events, questions}: ``events`` is
    how many events are told by then, and each question is {id, question, expected, family, probe}. A cut longer
    than the script is left out once an earlier cut is kept (3M and 4M on the 2M Long Haul);
    ``camr_engine.bench.haul.extend`` makes a script that has them."""
    events, probes = load_events(folder), load_probes(folder)
    out = []
    key, pool = 0, None  # a cut where nothing new became askable asks the cut before's questions again
    for name, limit in cuts.items():
        if out and limit > events[-1]["cum_tokens"]:
            continue
        told = sum(1 for e in events if e["cum_tokens"] <= limit)
        tokens = events[told - 1]["cum_tokens"] if told else 0
        now = {p["id"] for p in askable(probes, tokens)}
        if now != pool:
            key, pool = tokens, now
        picked = sample(probes, key, per_family, per_family=True, seed=seed)
        out.append({"name": name, "tokens": tokens, "events": told,
                    "questions": [{"id": q["id"], "question": q["ask"], "expected": q["answer"], "family": q["family"],
                                   "probe": q} for q in picked]})
    return events, out


def grader(question: dict, answer: str) -> dict:
    """The rule verdict on one answer, for any contender."""
    g = grade(question["probe"], answer or "")
    return {"verdict": g.verdict, "right": g.verdict in RIGHT, "reason": g.reason}


def run_claude(model: str, folder: Path, names: list[str] | None = None, progress=print) -> dict:
    from camr_engine.bench.claude import Checkpoint, Claude

    events, cps = checkpoints(folder)
    if names:
        cps = [c for c in cps if c["name"] in names]
    history = [line(e) for e in events]
    runner = Claude()
    record = runner.run(model, history, [Checkpoint(c["name"], c["events"], c["questions"]) for c in cps],
                        grader=grader, task="longhaul", progress=progress)
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.longhaul")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("claude", help="Claude alone, no memory: the yardstick")
    c.add_argument("--model", required=True)
    c.add_argument("--dir", type=Path, required=True)
    c.add_argument("--cuts", nargs="*", help=f"some of {', '.join(CUTS)} (default: all)")
    s = sub.add_parser("show", help="print the checkpoints: questions per family at each cut")
    s.add_argument("--dir", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "show":
        _, cps = checkpoints(a.dir)
        for cp in cps:
            fams: dict[str, int] = {}
            for q in cp["questions"]:
                fams[q["family"]] = fams.get(q["family"], 0) + 1
            print(f"{cp['name']:>4}: {cp['tokens']:>9,} tokens, {cp['events']:>5} events, "
                  f"{len(cp['questions'])} questions {json.dumps(fams)}")
        return 0
    record = run_claude(a.model, a.dir, a.cuts)
    print(record.get("path"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
