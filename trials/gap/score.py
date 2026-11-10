#!/usr/bin/env python3
"""Read one or more results folders and write summary.json and summary.md.

    python score.py results/local-gemma4            # one folder
    python score.py results/local-gemma4 results/cloud --out results/local-gemma4

Each set-up may appear in only one of the folders given. See README.md.
"""
import argparse
import json
import os
import statistics
import sys
import unicodedata

from scoring import sign_test

ORDER = ["local_alone", "local_database", "chroma", "local_engine", "local_engine_noskills", "local_engine_nocheck",
         "cloud_alone", "cloud_engine"]
MEMORY_SETUPS = ["local_database", "chroma", "local_engine", "local_engine_noskills", "local_engine_nocheck"]
SIGN_PAIRS = [("local_engine", "local_alone"), ("local_engine", "local_database"), ("local_engine", "chroma"),
              ("local_engine", "local_engine_noskills"), ("local_engine", "local_engine_nocheck")]
TYPES = ["single", "multi", "reasoning"]


def norm_path(path):
    path = unicodedata.normalize("NFC", str(path)).replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def load(folders):
    """{setup: {task id: last record}} and the meta of each folder."""
    results, metas, source = {}, {}, {}
    for folder in folders:
        meta_path = os.path.join(folder, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as handle:
                metas[folder] = json.load(handle)
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".jsonl"):
                continue
            setup = name[:-len(".jsonl")]
            if setup in results:
                raise SystemExit("%s is in both %s and %s: give only one of them" % (setup, source[setup], folder))
            rows = {}
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        row = json.loads(line)
                        rows[row["id"]] = row          # a later line for the same id (a retry) replaces it
            if rows:
                results[setup] = rows
                source[setup] = folder
    return results, metas, source


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def cell(rows):
    n = len(rows)
    correct = sum(1 for row in rows if row.get("correct"))
    return {"n": n, "correct": correct, "accuracy": correct / n if n else None,
            "errors": sum(1 for row in rows if row.get("error")),
            "median_seconds": median([row.get("seconds") for row in rows if not row.get("error")]),
            "median_prompt_tokens": median([row.get("prompt_tokens") for row in rows if not row.get("error")]),
            "median_answer_tokens": median([row.get("answer_tokens") for row in rows if not row.get("error")])}


def groups(rows):
    """Rows keyed by (subject, type), with 'all' standing for every subject or every type."""
    out = {}
    for row in rows:
        for key in ((row["subject"], row["type"]), (row["subject"], "all"), ("all", row["type"]), ("all", "all")):
            out.setdefault(key, []).append(row)
    return out


def accuracy(rows_by_id):
    return {key: cell(rows) for key, rows in groups(rows_by_id.values()).items()}


def slices(ids, reference):
    """Named sets of task ids: all, each subject, each type, and knowledge (everything but reasoning)."""
    out = {"all": list(ids)}
    for task_id in ids:
        row = reference[task_id]
        out.setdefault("subject: " + row["subject"], []).append(task_id)
        out.setdefault("type: " + row["type"], []).append(task_id)
        if row["type"] != "reasoning":
            out.setdefault("knowledge (single + multi)", []).append(task_id)
    return out


def gap_closed(results, memory, local="local_alone", cloud="cloud_alone"):
    """(with memory - local alone) / (cloud alone - local alone), on the tasks all three answered."""
    if not all(name in results for name in (memory, local, cloud)):
        return {}
    ids = sorted(set(results[memory]) & set(results[local]) & set(results[cloud]))
    out = {}
    for name, members in slices(ids, results[local]).items():
        n = len(members)
        acc = {s: sum(1 for i in members if results[s][i].get("correct")) / n for s in (memory, local, cloud)}
        gap = acc[cloud] - acc[local]
        out[name] = {"n": n, "with_memory": acc[memory], "local_alone": acc[local], "cloud_alone": acc[cloud],
                     "gap_closed": (acc[memory] - acc[local]) / gap if gap > 0 else None}
    return out


def gap_text(entry):
    if entry["gap_closed"] is None:
        return "not defined (cloud is not better than local alone)"
    return "%.0f%%" % (100 * entry["gap_closed"])


def paired(results, a, b, only=None):
    """Sign test of a against b on the tasks both answered."""
    ids = sorted(set(results[a]) & set(results[b]))
    if only:
        ids = [i for i in ids if only(results[a][i])]
    a_only = sum(1 for i in ids if results[a][i].get("correct") and not results[b][i].get("correct"))
    b_only = sum(1 for i in ids if results[b][i].get("correct") and not results[a][i].get("correct"))
    both = sum(1 for i in ids if results[a][i].get("correct") and results[b][i].get("correct"))
    return {"a": a, "b": b, "n": len(ids), "both_right": both, "a_only": a_only, "b_only": b_only,
            "neither": len(ids) - both - a_only - b_only, "p": sign_test(a_only, b_only)}


def evidence_recall(rows_by_id):
    """Of the tasks that name evidence files: how often every one of them was among the excerpts."""
    with_evidence = [row for row in rows_by_id.values() if row.get("evidence")]
    out = {}
    reference = {row["id"]: row for row in with_evidence}
    for name, members in slices(sorted(reference), reference).items():
        every = some = 0
        for task_id in members:
            row = reference[task_id]
            got = {norm_path(p) for p in row.get("excerpt_paths") or []}
            want = [norm_path(p) for p in row["evidence"]]
            every += all(p in got for p in want)
            some += any(p in got for p in want)
        out[name] = {"n": len(members), "recall": every / len(members), "any": some / len(members)}
    return out


# ---------------------------------------------------------------- writing it out

def pct(value):
    return "–" if value is None else "%.1f%%" % (100 * value)


def num(value, digits=1):
    if value is None:
        return "–"
    return ("%." + str(digits) + "f") % value if digits else "%d" % round(value)


def table(header, rows):
    widths = [max(len(str(line[i])) for line in [header] + rows) for i in range(len(header))]
    def fmt(line):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(line, widths)) + " |"
    return "\n".join([fmt(header), "|" + "|".join("-" * (w + 2) for w in widths) + "|"] + [fmt(r) for r in rows])


def build(results, metas, source):
    setups = [s for s in ORDER if s in results] + sorted(s for s in results if s not in ORDER)
    summary = {"folders": source, "setups": {}, "gap_closed": {}, "sign_tests": [], "evidence_recall": {},
               "meta": metas}
    out = ["# Results summary", ""]
    for folder, meta in metas.items():
        out.append("- `%s`: local model `%s`, cloud model `%s`, burrow `%s`, %s" % (
            folder, meta.get("model"), meta.get("cloud_model"), (meta.get("burrow_sha256") or "–")[:12],
            meta.get("date")))
    out.append("")

    # 1. accuracy
    tables = {setup: accuracy(results[setup]) for setup in setups}
    out += ["## Accuracy overall", ""]
    rows = []
    for setup in setups:
        c = tables[setup][("all", "all")]
        rows.append([setup, c["n"], c["correct"], pct(c["accuracy"]), c["errors"], num(c["median_seconds"], 2),
                     num(c["median_prompt_tokens"], 0), num(c["median_answer_tokens"], 0)])
    out += [table(["set-up", "n", "right", "accuracy", "errors", "median s", "median prompt tokens",
                   "median answer tokens"], rows), ""]

    out += ["## Accuracy by set-up, subject and type", ""]
    rows = []
    for setup in setups:
        summary["setups"][setup] = {"%s / %s" % key: value for key, value in sorted(tables[setup].items())}
        keys = sorted(k for k in tables[setup] if k != ("all", "all"))
        keys.sort(key=lambda k: (k[0] == "all", k[0], k[1] == "all", TYPES.index(k[1]) if k[1] in TYPES else 9))
        for subject, kind in keys:
            c = tables[setup][(subject, kind)]
            rows.append([setup, subject, kind, c["n"], c["correct"], pct(c["accuracy"]),
                         num(c["median_seconds"], 2), num(c["median_prompt_tokens"], 0)])
    out += [table(["set-up", "subject", "type", "n", "right", "accuracy", "median s", "median prompt tokens"],
                  rows), ""]

    # 2. gap closed
    out += ["## Fraction of the capability gap closed", "",
            "gap closed = (local with memory − local alone) / (cloud alone − local alone), "
            "on the questions all three set-ups answered.", ""]
    if "local_alone" not in results or "cloud_alone" not in results:
        out += ["Not computed: this needs both `local_alone` and `cloud_alone` results.", ""]
    for memory in [s for s in MEMORY_SETUPS if s in results]:
        gap = gap_closed(results, memory)
        if not gap:
            continue
        summary["gap_closed"][memory] = gap
        rows = [[name, e["n"], pct(e["local_alone"]), pct(e["with_memory"]), pct(e["cloud_alone"]), gap_text(e)]
                for name, e in gap.items()]
        out += ["### %s" % memory, "",
                table(["slice", "n", "local alone", memory, "cloud alone", "gap closed"], rows), ""]

    # 3. sign tests
    out += ["## Sign tests", "",
            "Exact two-sided sign test on the questions where the two set-ups disagree.", ""]
    rows = []
    for a, b in SIGN_PAIRS:
        if a not in results or b not in results:
            rows.append(["%s vs %s" % (a, b), "all", "–", "–", "–", "missing results"])
            continue
        for label, only in (("all", None), ("knowledge (single + multi)", lambda r: r["type"] != "reasoning")):
            test = paired(results, a, b, only)
            test["slice"] = label
            summary["sign_tests"].append(test)
            rows.append(["%s vs %s" % (a, b), label, test["n"], test["a_only"], test["b_only"],
                         "p = %.4g" % test["p"]])
    out += [table(["pair", "slice", "n", "only first right", "only second right", "result"], rows), ""]

    # 4. evidence recall
    out += ["## Evidence recall", "",
            "Of the questions that name evidence files: the share where every evidence file was among the "
            "retrieved excerpts (\"all\"), and where at least one was (\"any\").", ""]
    rows = []
    for setup in setups:
        if not any(row.get("excerpt_paths") for row in results[setup].values()):
            continue
        recall = evidence_recall(results[setup])
        summary["evidence_recall"][setup] = recall
        for name, e in recall.items():
            rows.append([setup, name, e["n"], pct(e["recall"]), pct(e["any"])])
    out += [table(["set-up", "slice", "n", "all evidence files", "any evidence file"], rows) if rows
            else "No set-up here retrieved anything.", ""]
    return summary, "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folders", nargs="+", help="results folders")
    parser.add_argument("--out", help="where to write summary.json and summary.md (default: the first folder)")
    args = parser.parse_args()
    for folder in args.folders:
        if not os.path.isdir(folder):
            raise SystemExit("no folder %s" % folder)
    results, metas, source = load(args.folders)
    if not results:
        raise SystemExit("no results found")
    summary, text = build(results, metas, source)
    out = args.out or args.folders[0]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, ensure_ascii=False)
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(text)
    print("\nwrote %s and %s" % (os.path.join(out, "summary.json"), os.path.join(out, "summary.md")),
          file=sys.stderr)


if __name__ == "__main__":
    main()
