#!/usr/bin/env python3
"""Scores the real-repository results once, using the measures fixed in docs/report/evaluation-plan.md."""
import json
import math
import sys
from pathlib import Path

folder = Path(sys.argv[1])
rows = []
for file in sorted(folder.glob("*.jsonl")):
    for line in open(file):
        record = json.loads(line)
        record["repo"] = file.stem
        rows.append(record)
dropped = [row for row in rows if not row["gold"]]
rows = [row for row in rows if row["gold"]]


def measures(row, mode):
    files, gold = row[mode]["files"], set(row["gold"])
    return {"first": bool(files) and files[0] in gold, "any": bool(gold & set(files)), "all": gold <= set(files), "recall": len(gold & set(files)) / len(gold)}


def sign_test(a, b):
    """Exact two-sided sign test on the instances where the two modes disagree."""
    wins, losses = sum(x and not y for x, y in zip(a, b)), sum(y and not x for x, y in zip(a, b))
    n = wins + losses
    if n == 0:
        return wins, losses, 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(wins, losses) + 1)) / 2 ** n
    return wins, losses, min(1.0, 2 * tail)


def table(title, subset):
    print(f"\n{title}: {len(subset)} instances")
    print("mode    right file first   any changed file reached   every changed file reached   mean recall")
    for mode in ("search", "walk"):
        scores = [measures(row, mode) for row in subset]
        n = len(subset)
        print(f"{mode:7} {sum(s['first'] for s in scores):3}/{n}            {sum(s['any'] for s in scores):3}/{n}                     {sum(s['all'] for s in scores):3}/{n}                       {sum(s['recall'] for s in scores) / n:.3f}")
    for key in ("first", "any", "all"):
        walk, search = [measures(r, "walk")[key] for r in subset], [measures(r, "search")[key] for r in subset]
        wins, losses, p = sign_test(walk, search)
        print(f"  {key}: walk better on {wins}, search better on {losses}, exact sign test p = {p:.3f}")


print("dropped (the fix only added new files):", len(dropped))
table("All repositories", rows)
for repo in sorted({row["repo"] for row in rows}):
    table(repo, [row for row in rows if row["repo"] == repo])
print("\nGrowth")
for file in sorted(folder.glob("*.growth.json")):
    growth = json.load(open(file))
    name = file.name.split(".")[0]
    subset = [r for r in rows if r["repo"] == name]
    seconds = sorted(r[m]["seconds"] for r in subset for m in ("search", "walk"))
    answers = [r["answer_seconds"] for r in subset if "answer_seconds" in r]
    print(name, growth["stats"], "| repo MB", round(growth["repo_bytes"] / 1e6, 1), "| index MB", round(growth["index_bytes"] / 1e6, 1), "| first index s", round(growth["first_index_seconds"], 1),
          "| retrieve median s", round(seconds[len(seconds) // 2], 3), "max", round(seconds[-1], 3), "| answer mean s", round(sum(answers) / max(1, len(answers)), 1))
