#!/usr/bin/env python3
"""Checks tasks/knowledge.jsonl against the documents in vault/.

Run:  python3 tasks/check_knowledge.py
Exit code 0 when there are zero errors, 1 otherwise.
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(HERE, "..", "vault")
JSONL = os.path.join(HERE, "knowledge.jsonl")
EXPECTED = {("law", "single"): 25, ("law", "multi"): 15, ("software", "single"): 25, ("software", "multi"): 15}
FOLDER = {"law": "Law", "software": "Software"}

def squash(s):
    return re.sub(r"\s+", " ", s).strip()

def main():
    errors, items, files = [], [], {}
    def err(where, msg): errors.append(f"{where}: {msg}")

    def load(rel):
        if rel not in files:
            p = os.path.normpath(os.path.join(VAULT, rel))
            if not p.startswith(os.path.normpath(VAULT) + os.sep) or not os.path.isfile(p):
                files[rel] = None
            else:
                files[rel] = squash(open(p, encoding="utf-8").read())
        return files[rel]

    with open(JSONL, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                err(f"line {n}", "blank line"); continue
            try:
                items.append((n, json.loads(line)))
            except json.JSONDecodeError as e:
                err(f"line {n}", f"does not parse as JSON ({e})")

    ids = Counter(q.get("id") for _, q in items)
    for i, c in ids.items():
        if c > 1: err(str(i), f"id used {c} times")

    counts = Counter()
    for n, q in items:
        w = q.get("id") or f"line {n}"
        missing = [k for k in ("id", "subject", "type", "question", "must_include", "evidence") if k not in q]
        if missing:
            err(w, f"missing fields {missing}"); continue
        subj, typ, question = q["subject"], q["type"], q["question"]
        if subj not in FOLDER: err(w, f"bad subject {subj!r}")
        if typ not in ("single", "multi"): err(w, f"bad type {typ!r}")
        counts[(subj, typ)] += 1
        if not isinstance(question, str) or len(question.strip()) < 20: err(w, "question missing or too short")
        if re.search(r"according to the (document|text|passage)|document above|passage above", str(question), re.I):
            err(w, "question is not self-contained")

        ev = q["evidence"]
        if not isinstance(ev, list) or not ev:
            err(w, "no evidence"); ev = []
        ev_text = []
        for k, e in enumerate(ev):
            rel, quote = e.get("file", ""), e.get("quote", "")
            body = load(rel)
            if body is None:
                err(w, f"evidence file not found under vault/: {rel}"); continue
            if subj in FOLDER and not rel.startswith(FOLDER[subj] + "/"):
                err(w, f"evidence file {rel} is not in the {FOLDER[subj]} folder")
            sq = squash(quote)
            if not sq:
                err(w, f"evidence {k + 1} has an empty quote")
            elif sq not in body:
                err(w, f"quote not found verbatim in {rel}: {sq[:70]!r}")
            ev_text.append(sq.lower()); ev_text.append(body.lower())
        nfiles = len({e.get("file") for e in ev})
        if typ == "single" and len(ev) < 1: err(w, "single question needs one evidence entry")
        if typ == "multi" and (len(ev) < 2 or nfiles < 2):
            err(w, "multi question needs two evidence entries from two different files")

        groups = q["must_include"]
        if not isinstance(groups, list) or not (1 <= len(groups) <= 3):
            err(w, "must_include needs 1 to 3 groups"); groups = groups if isinstance(groups, list) else []
        ql = str(question).lower()
        for g, group in enumerate(groups, 1):
            if not isinstance(group, list) or not group or not all(isinstance(s, str) and s.strip() for s in group):
                err(w, f"group {g} must be a non-empty list of strings"); continue
            if not any(s.lower() in t for s in group for t in ev_text):
                err(w, f"group {g} {group} has no string found in its evidence")
            for s in group:
                if s.lower() in ql:
                    err(w, f"must_include string {s!r} appears in the question")

    for key, want in EXPECTED.items():
        if counts[key] != want: err("counts", f"{key[0]}/{key[1]}: have {counts[key]}, want {want}")

    print(f"questions: {len(items)}")
    for key in EXPECTED: print(f"  {key[0]:8s} {key[1]:6s} {counts[key]}")
    used = sorted(k for k, v in files.items() if v is not None)
    print(f"evidence files used: {len(used)}")
    print(f"errors: {len(errors)}")
    for e in errors: print("  ERROR", e)
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
