"""The suites from the command line.

  python -m engram.bench.suites list
  python -m engram.bench.suites sample babilong --n 2 --seed 0 --lengths 4k,16k
  python -m engram.bench.suites webdev
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from collections.abc import Sequence

from engram.bench.suites import HISTORIES, SUITES, module
from engram.bench.suites.common import data_dir

SOURCES = {"babilong": "RMT-team/babilong", "memoryagentbench": "ai-hyz/MemoryAgentBench",
           "math500": "HuggingFaceH4/MATH-500", "aime": "MathArena/aime_2025, MathArena/aime_2026",
           "harp": "github.com/aadityasingh/HARP", "longmemeval": "xiaowu0162/longmemeval-cleaned (S)",
           "webdev": "lmarena-ai/leaderboard-dataset (webdev)"}
SAMPLED_BY = {"babilong": "items per task, each story at every length", "memoryagentbench": "questions per context",
              "math500": "problems", "aime": "problems per year", "harp": "pairs (A and B share subject and level)",
              "longmemeval": "questions per question kind"}


def _first_sentence(doc: str | None) -> str:
    text = " ".join((doc or "").strip().split("\n\n")[0].split())
    if 0 < text.find(": ") < 60:
        text = text.split(": ", 1)[1]
    cut = text.find(". ")
    return text[: cut + 1] if cut > 0 else text


def cmd_list() -> int:
    print(f"data: {data_dir()}\n")
    for name, m in SUITES.items():
        print(f"{name:17} {SOURCES[name]}")
        print(f"{'':17} {_first_sentence(m.__doc__)}")
        print(f"{'':17} --n: {SAMPLED_BY[name]}")
    for name, m in HISTORIES.items():
        print(f"{name:17} {SOURCES[name]}  (a history, not items: writes {m.CSV_PATH.name})")
    return 0


def _options(suite: str, a: argparse.Namespace) -> dict:
    split = (lambda s: [x.strip() for x in s.split(",") if x.strip()])
    kw: dict = {}
    if suite == "babilong":
        if a.tasks:
            kw["tasks"] = split(a.tasks)
        if a.lengths:
            kw["lengths"] = split(a.lengths)
    elif suite == "memoryagentbench" and a.splits:
        kw["splits"] = tuple(split(a.splits))
    elif suite == "aime" and a.years:
        kw["years"] = tuple(int(y) for y in split(a.years))
    elif suite == "harp":
        if a.subject:
            kw["subject"] = a.subject
        if a.level:
            kw["level"] = a.level
    return kw


def cmd_sample(a: argparse.Namespace) -> int:
    m = module(a.suite)
    items = m.sample(a.n, a.seed, **_options(m.NAME, a))
    sizes = [it.length_tokens for it in items]
    print(f"{len(items)} items from {m.NAME} (n={a.n}, seed={a.seed})")
    if sizes:
        print(f"length in tokens: min {min(sizes):,}, median {int(statistics.median(sizes)):,}, max {max(sizes):,}")
    if m.NAME == "babilong":
        print("per length: " + ", ".join(f"{k} {v}" for k, v in Counter(it.meta["length"] for it in items).items()))
    for it in items[: a.show]:
        ans = it.answer if isinstance(it.answer, str) else " | ".join(it.answer)
        ans = " ".join(ans.split())
        print(f"- {it.summary()}\n  A: {ans[:100]}{'…' if len(ans) > 100 else ''}")
    if len(items) > a.show:
        print(f"… and {len(items) - a.show} more")
    return 0


def cmd_webdev(a: argparse.Namespace) -> int:
    from engram.bench.suites import webdev

    csv_path, summary_path, s = webdev.build(category=None if a.all_boards else webdev.CATEGORY)
    print(f"wrote {csv_path} ({s['rows']:,} rows on the {', '.join(s['category'])} board, {s['first_date']} to "
          f"{s['last_date']}, {s['publications']} publications)")
    print(f"wrote {summary_path}")
    for row in s["top_by_month"][-3:]:
        print(f"  {row['month']} top: {row['model']} ({row['organisation']}) {row['rating']:.0f}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engram.bench.suites", description="Hugging Face benchmark suites.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="the suites and where their data lives")
    s = sub.add_parser("sample", help="print a seeded sample with its lengths")
    s.add_argument("suite")
    s.add_argument("--n", type=int, default=2, help="items per group (see list)")
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--show", type=int, default=10, help="how many items to print")
    s.add_argument("--tasks", help="babilong: e.g. qa1,qa2")
    s.add_argument("--lengths", help="babilong: e.g. 4k,16k,1M")
    s.add_argument("--splits", help="memoryagentbench: Conflict_Resolution,Accurate_Retrieval")
    s.add_argument("--years", help="aime: e.g. 2025,2026")
    s.add_argument("--subject", help="harp: e.g. algebra")
    s.add_argument("--level", type=int, help="harp: 1-6")
    w = sub.add_parser("webdev", help="write the WebDev Arena rating history (CSV) and its summary (JSON)")
    w.add_argument("--all-boards", action="store_true", help="keep every board in the CSV, not only 'overall'")
    a = p.parse_args(argv)
    if a.cmd == "list":
        return cmd_list()
    if a.cmd == "sample":
        try:
            return cmd_sample(a)
        except KeyError as e:
            print(e.args[0], file=sys.stderr)
            return 2
    return cmd_webdev(a)


if __name__ == "__main__":
    sys.exit(main())
