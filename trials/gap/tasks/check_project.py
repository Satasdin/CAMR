#!/usr/bin/env python3
"""Checks trials/gap/tasks/project.jsonl against the snapshot in trials/gap/vault.

Run: python3 trials/gap/tasks/check_project.py
Exits 0 with "0 errors" when every task is sound.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / "project.jsonl"
VAULT = HERE.parent / "vault"
SINGLE, MULTI = 25, 15


def squash(text):
    return " ".join(text.split())


def main():
    errors = []
    tasks = []
    for number, line in enumerate(TASKS.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            tasks.append((number, json.loads(line)))
        except json.JSONDecodeError as problem:
            errors.append(f"line {number}: not JSON ({problem})")

    seen = set()
    counts = {"single": 0, "multi": 0}
    files = {}
    for number, task in tasks:
        name = task.get("id", f"line {number}")
        missing = [key for key in ("id", "subject", "type", "question", "must_include", "evidence") if key not in task]
        if missing:
            errors.append(f"{name}: missing {', '.join(missing)}")
            continue
        if name in seen:
            errors.append(f"{name}: id used twice")
        seen.add(name)
        if task["subject"] != "project":
            errors.append(f"{name}: subject is not 'project'")
        kind = task["type"]
        if kind not in counts:
            errors.append(f"{name}: type must be single or multi")
            continue
        counts[kind] += 1

        question = task["question"]
        if "burrow" not in question.lower():
            errors.append(f"{name}: question does not name the project")

        evidence = task["evidence"]
        if not evidence:
            errors.append(f"{name}: no evidence")
        if kind == "multi" and len({item["file"] for item in evidence}) < 2:
            errors.append(f"{name}: multi needs evidence from two different files")
        quotes, bodies, paths = [], [], []
        for item in evidence:
            path = VAULT / item["file"]
            if not path.is_file():
                errors.append(f"{name}: no such file {item['file']}")
                continue
            if item["file"] not in files:
                files[item["file"]] = squash(path.read_text(encoding="utf-8"))
            quote = squash(item["quote"])
            if not quote:
                errors.append(f"{name}: empty quote for {item['file']}")
            elif quote not in files[item["file"]]:
                errors.append(f"{name}: quote not found verbatim in {item['file']}: {quote[:70]}")
            quotes.append(quote.lower())
            bodies.append(files[item["file"]].lower())
            paths.append(item["file"].lower())

        groups = task["must_include"]
        if not 1 <= len(groups) <= 3:
            errors.append(f"{name}: must_include needs 1 to 3 groups, has {len(groups)}")
        for group in groups:
            if not group or not all(isinstance(text, str) and text.strip() for text in group):
                errors.append(f"{name}: empty must_include group or string")
                continue
            # A group is grounded when one of its strings is in a quote or in an evidence file (its text or its path).
            grounded = any(text.lower() in place for text in group for place in quotes + bodies + paths)
            if not grounded:
                errors.append(f"{name}: no string of {group} appears in the evidence")
            for text in group:
                if text.lower() in question.lower():
                    errors.append(f"{name}: must_include string {text!r} appears in the question")

    if counts["single"] != SINGLE:
        errors.append(f"expected {SINGLE} single, found {counts['single']}")
    if counts["multi"] != MULTI:
        errors.append(f"expected {MULTI} multi, found {counts['multi']}")

    for problem in errors:
        print("ERROR", problem)
    print(f"{len(tasks)} tasks: {counts['single']} single, {counts['multi']} multi, {len(files)} evidence files, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
