#!/usr/bin/env python3
"""Real-repository test (RQ3) and growth test (RQ4). See docs/report/evaluation-plan.md. Clones hold untrusted code: they are only read as text.

usage: run.py <burrow-binary> <swebench-test.json> <work-folder> <results-folder> <repo> [<repo> ...]
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

LIMIT = 30  # the latest instances per repository, fixed before any result was seen
binary, listing, work, results = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
repos = sys.argv[5:]
rows = json.load(open(listing))
ANSWER_TIMES = 5


def run(*command, cwd=None):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True, timeout=7200)


def gold_files(patch, clone):
    named = sorted(set(re.findall(r"^diff --git a/(\S+) b/", patch, flags=re.M)))
    return [path for path in named if (clone / path).exists()]


def stats(clone, store):
    line = run(binary, "stats", str(clone), "--store", str(store)).stdout.strip().split("\n")[-1]
    return line


results.mkdir(parents=True, exist_ok=False)
for repo in repos:
    name = repo.split("/")[1]
    chosen = sorted((row for row in rows if row["repo"] == repo), key=lambda row: row["created_at"])[-LIMIT:]
    clone, store = work / "clones" / name, work / "stores" / name
    if not clone.exists():
        clone.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", f"https://github.com/{repo}.git", str(clone))
    out = open(results / f"{name}.jsonl", "w")
    growth = {"repo": repo, "instances": len(chosen)}
    for number, row in enumerate(chosen):
        run("git", "-c", "core.hooksPath=/dev/null", "checkout", "--quiet", "--force", row["base_commit"], cwd=clone)
        began = time.time()
        run(binary, "index", str(clone), "--store", str(store))
        seconds = time.time() - began
        if number == 0:
            growth["first_index_seconds"] = seconds
            growth["stats"] = stats(clone, store)
            size = sum(path.stat().st_size for path in store.glob("index.sqlite*"))
            growth["index_bytes"] = size
            growth["repo_bytes"] = int(run("du", "-sk", "--", str(clone)).stdout.split()[0]) * 1024 - int(run("du", "-sk", "--", str(clone / ".git")).stdout.split()[0]) * 1024
        gold = gold_files(row["patch"], clone)
        record = {"id": row["instance_id"], "gold": gold, "refresh_seconds": seconds}
        for mode in ("search", "walk"):
            found = json.loads(run(binary, "find", str(clone), row["problem_statement"], "--mode", mode, "--json", "--store", str(store)).stdout.strip().split("\n")[-1])
            seen = []
            for piece in found["excerpts"]:
                if piece["path"] not in seen:
                    seen.append(piece["path"])
            record[mode] = {"files": seen, "seconds": found["seconds"], "characters": found["characters"]}
        if number < ANSWER_TIMES:
            answer = json.loads(run(binary, "ask", str(clone), row["problem_statement"], "--mode", "walk", "--json", "--store", str(store)).stdout.strip().split("\n")[-1])
            record["answer_seconds"] = answer["total_s"]
        out.write(json.dumps(record) + "\n")
        out.flush()
        print(repo, number + 1, "of", len(chosen), flush=True)
    (results / f"{name}.growth.json").write_text(json.dumps(growth, indent=1))
