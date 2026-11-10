#!/usr/bin/env python3
"""Build tasks/reasoning.jsonl: 50 questions from the GSM8K test split.

    python reasoning.py

The official file is downloaded once to work/gsm8k/test.jsonl. The 50 are chosen with
random.Random(20261110).sample, so the same 50 come out every time.
"""
import hashlib
import json
import os
import random
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl"
SEED = 20261110
COUNT = 50


def main():
    folder = os.path.join(HERE, "work", "gsm8k")
    source = os.path.join(folder, "test.jsonl")
    os.makedirs(folder, exist_ok=True)
    if not os.path.exists(source):
        with urllib.request.urlopen(URL, timeout=120) as response:
            data = response.read()
        with open(source, "wb") as handle:
            handle.write(data)
    with open(source, "rb") as handle:
        data = handle.read()
    digest = hashlib.sha256(data).hexdigest()

    rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    for number, row in enumerate(rows, 1):
        row["line"] = number
    chosen = random.Random(SEED).sample(rows, COUNT)

    tasks = []
    for number, row in enumerate(chosen, 1):
        answer = row["answer"].rsplit("####", 1)[1].strip().replace(",", "")
        float(answer)                                   # every answer must be a number
        tasks.append({"id": "gsm-%03d" % number, "subject": "maths", "type": "reasoning",
                      "question": row["question"].strip(), "answer": answer, "must_include": [],
                      "evidence": [], "source_line": row["line"]})

    os.makedirs(os.path.join(HERE, "tasks"), exist_ok=True)
    out = os.path.join(HERE, "tasks", "reasoning.jsonl")
    with open(out, "w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "tasks", "reasoning.source.json"), "w", encoding="utf-8") as handle:
        json.dump({"dataset": "GSM8K, test split", "url": URL, "sha256": digest, "rows_in_file": len(rows),
                   "kept_at": "work/gsm8k/test.jsonl", "chosen": COUNT,
                   "method": "random.Random(%d).sample(rows, %d), rows in file order" % (SEED, COUNT),
                   "source_lines": [task["source_line"] for task in tasks]}, handle, indent=1)
    print("%d rows in the file, sha256 %s" % (len(rows), digest))
    print("wrote %d tasks to %s" % (len(tasks), out))


if __name__ == "__main__":
    main()
