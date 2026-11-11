#!/usr/bin/env python3
"""Search, measured without a model: for every Evaluation 2 question with evidence, does vault_search return the evidence
sentence, how far into the result is it, and how much text came back.

  /usr/bin/python3 trials/connect/search_eval.py [label]      writes results/search-<label>.json
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run

def squash(text):
    text = re.sub(r"^\d+: ", "", text, flags=re.M)          # line numbers in excerpts
    return re.sub(r"\s+", " ", text).strip().lower()

def items():
    for name in ["knowledge", "project"]:
        path = os.path.join(run.REPO, "trials", "gap", "tasks", name + ".jsonl")
        for line in open(path, encoding="utf-8"):
            if line.strip():
                task = json.loads(line)
                if task.get("evidence"):
                    yield name, task

def main(label):
    run.prepare()
    burrow = run.Burrow()
    rows = []
    for kind, task in items():
        started = time.time()
        text, _ = burrow.call("vault_search", {"query": task["question"]})
        seconds = time.time() - started
        flat = squash(text)
        places = []
        for evidence in task["evidence"]:
            quote = squash(evidence.get("quote", ""))[:160]
            places.append(flat.find(quote) if quote else -1)
        rows.append({"id": task["id"], "kind": kind, "type": task.get("type"), "found": all(p >= 0 for p in places),
                     "some": any(p >= 0 for p in places), "position": max(places) if all(p >= 0 for p in places) else None,
                     "characters": len(text), "seconds": round(seconds, 3)})
    burrow.close()
    def summary(subset, name):
        n = len(subset)
        found = [r for r in subset if r["found"]]
        early = [r for r in found if r["position"] < 4000]
        print(f"  {name:22} {n:3} questions: all evidence {len(found):3} ({100*len(found)/n:4.0f}%), "
              f"within the first 4,000 characters {len(early):3} ({100*len(early)/n:4.0f}%), "
              f"median {sorted(r['characters'] for r in subset)[n//2]:6} characters, median {sorted(r['seconds'] for r in subset)[n//2]*1000:4.0f} ms")
    print(f"search {label}")
    summary(rows, "everything")
    for kind in ["knowledge", "project"]:
        for kind_type in sorted({r["type"] for r in rows if r["kind"] == kind}):
            summary([r for r in rows if r["kind"] == kind and r["type"] == kind_type], f"{kind} {kind_type}")
    run.save("search-" + label, rows)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "now")
