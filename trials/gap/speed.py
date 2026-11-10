#!/usr/bin/env python3
"""Retrieval speed before and after, on one stored index, on a quiet machine.

usage: speed.py <old-binary> <new-binary> <swebench-test.json> <clone> <store> <repo> <out.json>

Each of the repository's latest 30 bug reports is looked up in search and walk mode by each binary, three times over.
The time is the whole command, from start to exit, so it includes opening the index and embedding the question.
The index is not refreshed, so both binaries read exactly the same data."""
import json, statistics, subprocess, sys, time

old, new, listing, clone, store, repo, out = sys.argv[1:8]
rows = sorted((row for row in json.load(open(listing)) if row["repo"] == repo), key=lambda row: row["created_at"])[-30:]
result = {"repo": repo, "questions": len(rows), "rounds": 3, "runs": {}}
for label, binary in (("before", old), ("after", new)):
    for mode in ("search", "walk"):
        wall, inside = [], []
        for _ in range(3):
            for row in rows:
                began = time.perf_counter()
                done = subprocess.run([binary, "find", clone, row["problem_statement"], "--mode", mode, "--json", "--store", store],
                                      capture_output=True, text=True, timeout=600)
                wall.append(time.perf_counter() - began)
                inside.append(json.loads(done.stdout.strip().split("\n")[-1])["seconds"])
        result["runs"][f"{label}_{mode}"] = {
            "median_wall_s": statistics.median(wall), "p90_wall_s": sorted(wall)[int(len(wall) * 0.9)], "worst_wall_s": max(wall),
            "median_reported_s": statistics.median(inside),
        }
        print(label, mode, result["runs"][f"{label}_{mode}"], flush=True)
json.dump(result, open(out, "w"), indent=1)
