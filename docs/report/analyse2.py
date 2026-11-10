#!/usr/bin/env python3
"""Reads the saved answers of evaluation plan 2 (trials/results/gap-1) and writes every number, table and chart
Chapter 5 uses. Nothing is typed into the report by hand: run this, then build.

usage: analyse2.py            writes generated2/*.md, generated2/numbers.json and figures/v2/chart-*.png"""
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent.parent / "trials" / "results" / "gap-1"
OUT = HERE / "generated2"
MAIN, SMALL, CLOUD = "gemma4-12b", "qwen3.5-4b", "cloud-sonnet"
NAMES = {
    "local_alone": "Model alone", "local_database": "Plain retrieval", "chroma": "Vector database (Chroma)",
    "local_engine": "Burrow engine", "local_engine_noskills": "Engine without skills", "local_engine_nocheck": "Engine without the check",
    "cloud_alone": "Cloud model alone", "cloud_engine": "Cloud model with Burrow",
}
GROUPS = [("Knowledge, one fact", lambda r: r["type"] == "single"), ("Knowledge, several facts", lambda r: r["type"] == "multi"),
          ("Reasoning", lambda r: r["type"] == "reasoning")]
SUBJECTS = [("Kenyan law", "law"), ("2026 software", "software"), ("Private project", "project"), ("Arithmetic reasoning", "maths")]


def load(folder, setup):
    path = RESULTS / folder / f"{setup}.jsonl"
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["id"]] = row
    return rows


def right(rows, keep=lambda r: True):
    chosen = [r for r in rows.values() if keep(r)]
    return sum(bool(r.get("correct")) for r in chosen), len(chosen)


def percent(pair):
    return f"{pair[0]} of {pair[1]} ({100 * pair[0] / pair[1]:.0f}%)" if pair[1] else "-"


def sign(a, b, keep=lambda r: True):
    """Exact two-sided sign test on the questions both answered. Returns wins for a, wins for b, p."""
    ids = [i for i in a if i in b and keep(a[i])]
    up = sum(1 for i in ids if a[i].get("correct") and not b[i].get("correct"))
    down = sum(1 for i in ids if b[i].get("correct") and not a[i].get("correct"))
    n = up + down
    if n == 0:
        return up, down, 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(up, down) + 1)) / 2 ** n
    return up, down, min(1.0, 2 * tail)


def gap(memory, alone, ceiling, keep=lambda r: True):
    m, n = right(memory, keep)
    a, _ = right(alone, keep)
    c, k = right(ceiling, keep)
    # With floor and ceiling a few questions apart the fraction swings wildly on one answer, so it is not reported.
    if not n or not k or (c - a) / k < 0.10:
        return None
    return (m - a) / (c - a)


def median(rows, key, keep=lambda r: True):
    values = [r[key] for r in rows.values() if keep(r) and isinstance(r.get(key), (int, float))]
    return statistics.median(values) if values else None


def evidence_files():
    """The files each question's answer is in, read from the task files (the harness saved them in a form that cannot be compared)."""
    files = {}
    root = HERE.parent.parent / "trials" / "gap" / "tasks"
    for name in ("knowledge", "project"):
        for line in (root / f"{name}.jsonl").read_text().splitlines():
            if line.strip():
                task = json.loads(line)
                files[task["id"]] = {item["file"] for item in task.get("evidence", [])}
    return files


EVIDENCE = evidence_files()


def recall(rows, keep=lambda r: True):
    """On how many questions every file holding the answer was among the files shown."""
    chosen = [r for r in rows.values() if keep(r) and EVIDENCE.get(r["id"])]
    hit = sum(1 for r in chosen if EVIDENCE[r["id"]] <= set(r.get("excerpt_paths") or []))
    return hit, len(chosen)


def wrong_split(rows, keep=lambda r: True):
    """Wrong answers split by whether the files holding the answer had been shown."""
    wrong = [r for r in rows.values() if keep(r) and EVIDENCE.get(r["id"]) and not r.get("correct")]
    shown = sum(1 for r in wrong if EVIDENCE[r["id"]] <= set(r.get("excerpt_paths") or []))
    return shown, len(wrong) - shown


def fmt_p(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def table(caption, widths, header, rows):
    lines = [f"!tab {caption}", "!widths " + ",".join(str(w) for w in widths), "| " + " | ".join(header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def extras(data, numbers):
    """The appendix tables, the example table and the charts."""
    import re
    root = HERE.parent.parent
    # Every automated test.
    log = root / "trials" / "results" / "gap-1" / "unit-tests-evaluation-2.log"
    if log.exists():
        found = re.findall(r"Test Case '-\[(\w+)\.(\w+) (\w+)\]' (passed|failed) \(([\d.]+) seconds\)", log.read_text())
        lines = ["!tab Table A5.1: Every automated test on the frozen source", "!widths 1.5,3.5,0.6,0.6", "| Suite | Test | Result | Seconds |"]
        for _, suite, name, result, seconds in sorted(found, key=lambda r: (r[1], r[2])):
            lines.append(f"| {suite} | `{name}` | {result.capitalize()} | {float(seconds):.3f} |")
        (OUT / "tests.md").write_text("\n".join(lines) + "\n")
        numbers["tests"] = {"passed": sum(1 for r in found if r[3] == "passed"), "failed": sum(1 for r in found if r[3] == "failed")}
    # Every question.
    tasks = {}
    for name in ("knowledge", "project", "reasoning"):
        for line in (root / "trials" / "gap" / "tasks" / f"{name}.jsonl").read_text().splitlines():
            if line.strip():
                task = json.loads(line)
                tasks[task["id"]] = task
    local, cloud = data[MAIN], data[CLOUD]
    mark = lambda rows, i: "-" if i not in rows else ("Right" if rows[i].get("correct") else "Wrong")
    lines = ["!tab Table A6.1: Every scored question and its result (Gemma 4 12B and the cloud model)", "!widths 0.8,0.6,0.7,0.8,0.7,0.7,0.7,0.9",
             "| Question | Kind | Alone | Plain retrieval | Chroma | Engine | Cloud alone | Cloud with Burrow |"]
    kinds = {"single": "One fact", "multi": "Several", "reasoning": "Reasoning"}
    for i in sorted(tasks):
        lines.append(f"| {i} | {kinds[tasks[i]['type']]} | " + " | ".join(mark(rows, i) for rows in (
            local["local_alone"], local["local_database"], local["chroma"], local["local_engine"], cloud["cloud_alone"], cloud["cloud_engine"])) + " |")
    (OUT / "questions.md").write_text("\n".join(lines) + "\n")
    # One example of each kind.
    def first(prefix):
        return tasks[sorted(i for i in tasks if i.startswith(prefix))[0]]
    lines = ["!tab Table A3.7: One question of each kind with its answer key", "!widths 1.1,3.6,1.6", "| Kind | Question | Key |"]
    for label, prefix in (("Law, one fact", "law-s"), ("Software, several facts", "sw-m"), ("Private project, one fact", "proj-s"), ("Reasoning", "gsm")):
        task = first(prefix)
        key = task.get("answer") or "; ".join(" or ".join(group) for group in task["must_include"])
        lines.append(f"| {label} | {task['question'].replace('|', '/')[:420]} | {str(key).replace('|', '/')} |")
    (OUT / "examples.md").write_text("\n".join(lines) + "\n")
    charts(data, numbers)


def charts(data, numbers):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = HERE / "figures" / "v2"
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
    ink, grid = "#1f2933", "#d5dbe1"
    colours = {"local_alone": "#9aa5b1", "local_database": "#e0861a", "chroma": "#7b61c4", "local_engine": "#1a9e77", "cloud_alone": "#2f6fde", "cloud_engine": "#17458f"}
    cloud = data[CLOUD]

    def bars(folder, label, name):
        local = data[folder]
        sets = [(s, local[s]) for s in ("local_alone", "local_database", "chroma", "local_engine") if local[s]]
        sets += [(s, cloud[s]) for s in ("cloud_alone", "cloud_engine") if cloud[s]]
        if len(sets) < 3:
            return
        fig, ax = plt.subplots(figsize=(6.4, 3.3))
        width = 0.8 / len(sets)
        for k, (setup, rows) in enumerate(sets):
            values = []
            for _, keep in GROUPS:
                got, n = right(rows, keep)
                values.append(100 * got / n if n else 0)
            xs = [g + (k - (len(sets) - 1) / 2) * width for g in range(len(GROUPS))]
            drawn = ax.bar(xs, values, width * 0.92, color=colours[setup], label=NAMES[setup], hatch="//" if setup.startswith("cloud") else None,
                           edgecolor="white", linewidth=0.6)
            for bar, value in zip(drawn, values):
                ax.text(bar.get_x() + bar.get_width() / 2, value + 1.2, f"{value:.0f}", ha="center", va="bottom", fontsize=6.5, color=ink)
        ax.set_xticks(range(len(GROUPS)), [name for name, _ in GROUPS])
        ax.set_ylabel("Answers right (%)")
        ax.set_ylim(0, 108)
        ax.yaxis.grid(True, color=grid, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.legend(ncol=3, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12))
        fig.tight_layout()
        fig.savefig(figures / name, dpi=220)
        plt.close(fig)

    bars(MAIN, "Gemma 4 12B", "chart-accuracy-main.png")
    bars(SMALL, "Qwen3.5 4B", "chart-accuracy-small.png")

    curve = numbers.get("sweep")
    if curve:
        fig, ax = plt.subplots(figsize=(6.0, 3.0))
        xs = [point["tokens"] for point in curve]
        ys = [100 * point["right"] / point["n"] for point in curve]
        ax.plot(xs, ys, color=colours["local_engine"], marker="o", linewidth=2)
        for point, x, y in zip(curve, xs, ys):
            ax.annotate(f"{point['characters']:,} characters", (x, y), textcoords="offset points", xytext=(7, 4) if point["characters"] == 2000 else (6, -11), fontsize=7, color=ink)
        ax.set_xlabel("Median tokens read per answer")
        ax.set_ylabel("Knowledge answers right (%)")
        ax.yaxis.grid(True, color=grid, linewidth=0.6)
        ax.set_axisbelow(True)
        fig.tight_layout()
        fig.savefig(figures / "chart-sweep.png", dpi=220)
        plt.close(fig)

    speed = RESULTS / "speed-django.json"
    if speed.exists():
        runs = json.loads(speed.read_text())["runs"]
        fig, ax = plt.subplots(figsize=(5.2, 2.8))
        labels = ["Search", "Search, then links"]
        before = [runs["before_search"]["median_wall_s"], runs["before_walk"]["median_wall_s"]]
        after = [runs["after_search"]["median_wall_s"], runs["after_walk"]["median_wall_s"]]
        for offset, values, colour, label in ((-0.2, before, "#9aa5b1", "Before"), (0.2, after, colours["local_engine"], "After")):
            drawn = ax.bar([x + offset for x in range(2)], values, 0.38, color=colour, label=label)
            for bar, value in zip(drawn, values):
                ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f} s", ha="center", va="bottom", fontsize=7.5, color=ink)
        ax.set_xticks(range(2), labels)
        ax.set_ylabel("Median seconds per lookup")
        ax.yaxis.grid(True, color=grid, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        fig.savefig(figures / "chart-speed.png", dpi=220)
        plt.close(fig)
        numbers["speed"] = runs


def main():
    OUT.mkdir(exist_ok=True)
    numbers = {}
    data = {folder: {setup: load(folder, setup) for setup in NAMES} for folder in (MAIN, SMALL, CLOUD)}
    cloud_alone, cloud_engine = data[CLOUD]["cloud_alone"], data[CLOUD]["cloud_engine"]
    knowledge = lambda r: r["type"] != "reasoning"

    for folder, label, number in ((MAIN, "Gemma 4 12B", "5.4"), (SMALL, "Qwen3.5 4B", "A3.1")):
        local = data[folder]
        if not local["local_alone"]:
            continue
        rows = []
        for setup in ("local_alone", "local_database", "chroma", "local_engine"):
            if local[setup]:
                rows.append([NAMES[setup]] + [percent(right(local[setup], keep)) for _, keep in GROUPS])
        for setup, source in (("cloud_alone", cloud_alone), ("cloud_engine", cloud_engine)):
            if source:
                rows.append([NAMES[setup]] + [percent(right(source, keep)) for _, keep in GROUPS])
        (OUT / f"accuracy-{folder}.md").write_text(table(
            f"Table {number}: Answers right by set-up and task type, {label}", [1.9, 1.4, 1.5, 1.3],
            ["Set-up"] + [name for name, _ in GROUPS], rows))
        numbers[folder] = {setup: {name: right(local[setup], keep) for name, keep in GROUPS} for setup in local if local[setup]}

    numbers["cloud"] = {setup: {name: right(source, keep) for name, keep in GROUPS}
                        for setup, source in (("cloud_alone", cloud_alone), ("cloud_engine", cloud_engine)) if source}

    # Per subject, main model.
    local = data[MAIN]
    rows = []
    for name, subject in SUBJECTS:
        keep = lambda r, s=subject: r["subject"] == s
        row = [name]
        for setup in ("local_alone", "local_database", "chroma", "local_engine"):
            row.append(percent(right(local[setup], keep)) if local[setup] else "-")
        row.append(percent(right(cloud_alone, keep)) if cloud_alone else "-")
        row.append(percent(right(cloud_engine, keep)) if cloud_engine else "-")
        rows.append(row)
    (OUT / "subjects.md").write_text(table(
        "Table A3.2: Answers right by subject, Gemma 4 12B and the cloud model", [1.1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
        ["Subject", "Alone", "Plain retrieval", "Chroma", "Engine", "Cloud alone", "Cloud with Burrow"], rows))

    # Gap closed.
    rows = []
    gaps = {}
    for folder, label in ((MAIN, "Gemma 4 12B"), (SMALL, "Qwen3.5 4B")):
        local = data[folder]
        if not local["local_engine"] or not cloud_alone:
            continue
        for name, keep in GROUPS + [("All knowledge", knowledge)]:
            for setup in ("local_database", "chroma", "local_engine"):
                value = gap(local[setup], local["local_alone"], cloud_alone, keep)
                gaps[f"{folder}|{name}|{setup}"] = value
            rows.append([label, name, percent(right(local["local_alone"], keep)), percent(right(cloud_alone, keep))] + [
                "not reported" if gaps[f"{folder}|{name}|{s}"] is None else f"{100 * gaps[f'{folder}|{name}|{s}']:.0f}%"
                for s in ("local_database", "chroma", "local_engine")])
    (OUT / "gap.md").write_text(table(
        "Table 5.5: Fraction of the capability gap closed (Equation 3.1), against the cloud model alone", [0.9, 1.2, 1.0, 1.0, 0.8, 0.7, 0.7],
        ["Local model", "Task type", "Floor: model alone", "Ceiling: cloud alone", "Plain retrieval", "Chroma", "Engine"], rows))
    numbers["gap"] = gaps

    # Cost.
    rows = []
    for folder, label in ((MAIN, "Gemma 4 12B"), (SMALL, "Qwen3.5 4B")):
        local = data[folder]
        for setup in ("local_alone", "local_database", "chroma", "local_engine"):
            if not local[setup]:
                continue
            rows.append([label, NAMES[setup], f"{median(local[setup], 'prompt_tokens', knowledge):.0f}",
                         f"{median(local[setup], 'seconds', knowledge):.1f}",
                         "-" if not median(local[setup], 'retrieve_s', knowledge) else f"{median(local[setup], 'retrieve_s', knowledge):.2f}",
                         percent(recall(local[setup], knowledge)) if setup != "local_alone" else "-"])
    for setup, source in (("cloud_alone", cloud_alone), ("cloud_engine", cloud_engine)):
        if source:
            rows.append(["Claude", NAMES[setup], f"{median(source, 'prompt_tokens', knowledge):.0f}", f"{median(source, 'seconds', knowledge):.1f}", "-",
                         percent(recall(source, knowledge)) if setup == "cloud_engine" else "-"])
    (OUT / "cost.md").write_text(table(
        "Table 5.6: Cost of an answer on knowledge questions: tokens read, seconds, and whether the evidence was retrieved", [0.9, 1.6, 0.8, 0.8, 0.9, 1.2],
        ["Model", "Set-up", "Median tokens read", "Median seconds", "Median seconds before the model", "Every evidence file retrieved"], rows))

    # Where the wrong answers came from.
    rows = []
    split = {}
    for folder, label in ((MAIN, "Gemma 4 12B"), (SMALL, "Qwen3.5 4B")):
        local = data[folder]
        for setup in ("local_database", "chroma", "local_engine"):
            if not local[setup]:
                continue
            shown, missing = wrong_split(local[setup], knowledge)
            split[f"{folder}|{setup}"] = (shown, missing)
            rows.append([label, NAMES[setup], shown + missing, missing, shown])
    if cloud_engine:
        shown, missing = wrong_split(cloud_engine, knowledge)
        split["cloud|cloud_engine"] = (shown, missing)
        rows.append(["Claude", NAMES["cloud_engine"], shown + missing, missing, shown])
    (OUT / "wrong.md").write_text(table(
        "Table A3.6: Wrong knowledge answers, by whether the files holding the answer were shown to the model", [0.9, 1.9, 0.9, 1.4, 1.4],
        ["Model", "Set-up", "Wrong answers", "A needed file was not shown", "Every needed file was shown"], rows))
    numbers["wrong"] = split

    # Sign tests.
    rows = []
    tests = {}
    for folder, label in ((MAIN, "Gemma 4 12B"), (SMALL, "Qwen3.5 4B")):
        local = data[folder]
        if not local["local_engine"]:
            continue
        pairs = [("local_engine", "local_alone"), ("local_engine", "local_database"), ("local_engine", "chroma")]
        if folder == MAIN:
            pairs += [("local_engine", "local_engine_noskills"), ("local_engine", "local_engine_nocheck")]
        for a, b in pairs:
            if not local[b]:
                continue
            for name, keep in (("Knowledge", knowledge), ("Reasoning", lambda r: r["type"] == "reasoning")):
                up, down, p = sign(local[a], local[b], keep)
                tests[f"{folder}|{a}|{b}|{name}"] = (up, down, p)
                rows.append([label, f"{NAMES[a]} against {NAMES[b].lower()}", name, up, down, fmt_p(p)])
    (OUT / "sign.md").write_text(table(
        "Table A3.3: Paired comparisons by exact sign test", [0.9, 2.5, 0.9, 0.7, 0.7, 0.7],
        ["Model", "Comparison", "Questions", "First right only", "Second right only", "p"], rows))
    numbers["sign"] = tests

    # What the engine did.
    engine = data[MAIN]["local_engine"]
    if engine:
        routes = Counter((r["type"] == "reasoning", (r.get("extra") or r).get("route", {}).get("mode", "?")) for r in engine.values())
        skills = Counter(((r.get("extra") or r).get("skills") or ["none"])[0] for r in engine.values())
        retried = sum(1 for r in engine.values() if (r.get("extra") or r).get("retried"))
        named = sum((r.get("extra") or r).get("citations", {}).get("named", 0) for r in engine.values())
        missing = sum((r.get("extra") or r).get("citations", {}).get("not_shown", 0) for r in engine.values())
        numbers["engine"] = {"routes": {f"{'reasoning' if k[0] else 'knowledge'}|{k[1]}": v for k, v in routes.items()},
                             "skills": dict(skills), "retried": retried, "citations_named": named, "citations_not_shown": missing}
        rows = [[("Reasoning" if k[0] else "Knowledge"), {"none": "Vault left out", "search": "Search", "walk": "Search, then links"}.get(k[1], k[1]), v]
                for k, v in sorted(routes.items())]
        text = table("Table A3.4: What the engine decided, Gemma 4 12B", [1.5, 2.2, 1.0], ["Questions", "Decision", "Count"], rows)
        text += "\n" + table("Table A3.5: The method handed to the model, Gemma 4 12B", [2.6, 1.0], ["Skill", "Questions"],
                             [[k, v] for k, v in skills.most_common()])
        (OUT / "decisions.md").write_text(text)

    # Budget sweep.
    sweep = []
    for size in (2000, 4000, 8000, 32000):
        rows_ = load(MAIN, f"local_engine_c{size}")
        if rows_:
            sweep.append((size, rows_))
    if sweep and data[MAIN]["local_engine"]:
        fitted = {i: r for i, r in data[MAIN]["local_engine"].items() if knowledge(r)}
        budget = statistics.median([(r.get("extra") or r).get("budget_characters", 0) for r in fitted.values()])
        sweep.append((int(budget), fitted))
        sweep.sort(key=lambda pair: pair[0])
        alone, ceiling = data[MAIN]["local_alone"], cloud_alone
        rows = []
        curve = []
        for size, rows_ in sweep:
            got, n = right(rows_, knowledge)
            tokens = median(rows_, "prompt_tokens", knowledge)
            value = gap(rows_, alone, ceiling, knowledge)
            a, _ = right(alone, knowledge)
            per_thousand = (got - a) / n * 100 / (tokens / 1000) if tokens else 0
            curve.append({"characters": size, "right": got, "n": n, "tokens": tokens, "gap": value, "seconds": median(rows_, "seconds", knowledge),
                          "points_per_1000_tokens": per_thousand})
            rows.append([f"{size:,}" + (" (fitted)" if size == int(budget) else ""), percent((got, n)), f"{tokens:.0f}",
                         "-" if value is None else f"{100 * value:.0f}%", f"{per_thousand:.1f}", f"{median(rows_, 'seconds', knowledge):.1f}"])
        (OUT / "sweep.md").write_text(table(
            "Table 5.7: How much of the vault the model is shown, against what it gains, Gemma 4 12B, knowledge questions", [1.3, 1.3, 0.9, 0.9, 1.2, 0.8],
            ["Characters shown", "Answers right", "Median tokens read", "Gap closed", "Points gained per 1,000 tokens", "Median seconds"], rows))
        numbers["sweep"] = curve

    extras(data, numbers)
    (OUT / "numbers.json").write_text(json.dumps(numbers, indent=1, default=str))
    print(json.dumps(numbers, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
