#!/usr/bin/env python3
"""Writes the long appendix tables from the saved results."""
import re, statistics as st
from pathlib import Path
import analyse as A
G = Path(__file__).parent / "generated"
G.mkdir(exist_ok=True)
# automated tests
log = (A.ROOT / "trials/results/unit-tests-evaluation-1.log").read_text()
rows = re.findall(r"Test Case '-\[(\w+)\.(\w+) (\w+)\]' (passed|failed) \(([\d.]+) seconds\)", log)
assert len(rows) == 186, len(rows)
out = ["!tab Table A5.1: Every automated test at tag evaluation-1", "!widths 1.5,3.5,0.6,0.6", "| Suite | Test | Result | Seconds |"]
for mod, suite, name, res, sec in sorted(rows, key=lambda r: (r[1], r[2])):
    out.append(f"| {suite} | `{name}` | {res.capitalize()} | {float(sec):.3f} |")
(G / "tests.md").write_text("\n".join(out) + "\n")
cnt = {}
for _, suite, *_r in rows: cnt[suite] = cnt.get(suite, 0) + 1
print(sorted(cnt.items(), key=lambda x: -x[1]), sum(float(r[4]) for r in rows))
# held
H = A.held()
out = []
n = 1
for p in A.PROJECTS:
    out += [f"!tab Table A6.{n}: Project {p}, session by session (T = task passed, D = decision broken, E = decision check errored, N = said it did not know)", "!widths 0.8,1,0.75,0.75,0.75,0.75,0.75,0.75,0.75,0.75,0.75",
            "| Session | Category | 4B none | 4B search | 4B walk | 8B none | 8B search | 8B walk | 1.7B none | 1.7B search | 1.7B walk |"]
    n += 1
    ids = sorted({x["session"] for x in H if x["project"] == p})
    for s in ids:
        cat = next(x["category"] for x in H if x["project"] == p and x["session"] == s)
        cells = []
        for m, _ in A.MODELS:
            for mo in A.MODES:
                x = next(y for y in H if y["project"] == p and y["session"] == s and y["model"] == m and y["mode"] == mo)
                f = ("T" if x["task_passed"] else "") + ("D" if x["decision_broken"] else "") + ("E" if x["decision_check_errored"] else "") + ("N" if x["said_dont_know"] else "")
                cells.append(f or "-")
        out.append(f"| {s} | {cat} | " + " | ".join(cells) + " |")
    out.append("")
(G / "held.md").write_text("\n".join(out))
# real
R = A.real()
out = ["!tab Table A7.1: The 101 real bug fixes (any = a changed file was reached; every = all changed files were reached)", "!widths 2.3,0.6,0.7,0.7,0.7,0.7,0.8,0.8", "| Instance | Changed files | Search any | Search every | Walk any | Walk every | Search s | Walk s |"]
yn = lambda b: "Yes" if b else "No"
for r in A.REPOS:
    for x in R[r]:
        s, w = A.hits(x, "search"), A.hits(x, "walk")
        out.append(f"| `{x['id']}` | {len(x['gold'])} | {yn(s['any'])} | {yn(s['all'])} | {yn(w['any'])} | {yn(w['all'])} | {x['search']['seconds']:.2f} | {x['walk']['seconds']:.2f} |")
(G / "real.md").write_text("\n".join(out) + "\n")
