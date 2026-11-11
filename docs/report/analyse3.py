#!/usr/bin/env python3
"""Reads the saved answers of evaluation plan 3 (trials/ledger/results) and writes every number, table and chart the
report uses for it. Nothing is typed into the report by hand: run this, then build.

usage: /usr/bin/python3 analyse3.py     writes generated3/*.md, generated3/numbers.json and figures/v3/chart-eval3.png"""
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent.parent / "trials" / "ledger" / "results"
OUT = HERE / "generated3"
SMALL, LARGE = "burrow-qwen3-4b-16k", "burrow-gemma4-12b-16k"
NAMES = {SMALL: "Qwen3 4B", LARGE: "Gemma 4 12B"}


def load(name):
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def sign(pairs):
    """Exact two-sided sign test on paired outcomes [(a_right, b_right)]. Returns wins for a, wins for b, p."""
    up = sum(1 for a, b in pairs if a and not b)
    down = sum(1 for a, b in pairs if b and not a)
    n = up + down
    if n == 0:
        return up, down, 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(up, down) + 1)) / 2 ** n
    return up, down, min(1.0, 2 * tail)


def fmt_p(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def table(caption, widths, header, rows):
    lines = [f"!tab {caption}", "!widths " + ",".join(str(w) for w in widths), "| " + " | ".join(header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def count(rows, key="right"):
    return sum(bool(r.get(key)) for r in rows), len(rows)


def of(pair):
    return f"{pair[0]} of {pair[1]}"


def median(rows, key):
    values = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return statistics.median(values) if values else None


def resume(numbers, tables):
    rows = load("e1")
    if not rows:
        return
    out, table_rows = {}, []
    for a, b in [(SMALL, LARGE), (LARGE, SMALL)]:
        for arm in ["fresh", "paste", "sessions", "ledger"]:
            mine = [r for r in rows if r["from"] == a and r["arm"] == arm]
            out[f"{a}>{b}:{arm}"] = {"right": count(mine), "tokens": median(mine, "prompt_tokens")}
    names = {"fresh": "Nothing", "paste": "The transcript pasted in", "sessions": "Today's session tools", "ledger": "The Ledger (burrow_resume)"}
    for arm in ["fresh", "paste", "sessions", "ledger"]:
        cells = [names[arm]]
        for a, b in [(SMALL, LARGE), (LARGE, SMALL)]:
            item = out[f"{a}>{b}:{arm}"]
            cells += [of(item["right"]), f"{item['tokens']:,.0f}" if item["tokens"] is not None else "-"]
        table_rows.append(cells)
    tests = {}
    key = lambda r: (r["from"], r["task"], r["probe"])
    by = {arm: {key(r): r for r in rows if r["arm"] == arm} for arm in ["paste", "sessions", "ledger"]}
    for other in ["paste", "sessions"]:
        pairs = [(by["ledger"][k]["right"], by[other][k]["right"]) for k in by["ledger"] if k in by[other]]
        tests[other] = sign(pairs)
    numbers["e1"] = {"cells": out, "ledger_vs": {k: list(v) for k, v in tests.items()}}
    tables["e1-resume.md"] = table(
        "Table 5.10: A model that lost its memory carries on a conversation: answers right of 15 and median prompt tokens",
        [1.9, 0.9, 0.9, 0.9, 0.9],
        ["Given to model B", "Qwen3 4B to Gemma, right", "Tokens", "Gemma to Qwen3 4B, right", "Tokens"], table_rows)


def notes(numbers, tables):
    rows = load("e2")
    teacher = load("e2-teacher")
    if not rows:
        return
    # The first run cut tool results at 12,000 characters, so the notes never reached the model (evaluation-plan-3.md).
    # The two Burrow arms come from the rerun with whole results when it exists; "alone" and "Claude alone" used no tools.
    rerun = load("e2b")
    first_run = {arm: count([r for r in rows if r["arm"] == arm]) for arm in ["engine", "engine+notes"]}
    if rerun:
        rows = [r for r in rows if r["arm"] in ("alone", "claude-alone")] + rerun
    arms = ["alone", "engine", "engine+notes", "claude-alone"]
    names = {"alone": "Qwen3 4B alone", "engine": "Qwen3 4B with Burrow", "engine+notes": "Qwen3 4B with Burrow and Claude's notes", "claude-alone": "Claude alone"}
    out, table_rows = {}, []
    for arm in arms:
        mine = [r for r in rows if r["arm"] == arm]
        single = count([r for r in mine if r["type"] == "single"])
        multi = count([r for r in mine if r["type"] == "multi"])
        out[arm] = {"all": count(mine), "single": single, "multi": multi,
                    "saw_notes": sum(bool(r.get("saw_notes")) for r in mine)}
        table_rows.append([names[arm], of(single), of(multi), of(count(mine))])
    by = {arm: {r["task"]: r for r in rows if r["arm"] == arm} for arm in arms}
    pairs = [(by["engine+notes"][t]["right"], by["engine"][t]["right"]) for t in by["engine"] if t in by["engine+notes"]]
    test = sign(pairs)
    kept = None
    if teacher:
        kept = {"answered": count(teacher["rows"]), "commits": sum(r.get("commits", 0) for r in teacher["rows"]), "dropped": len(teacher.get("dropped", []))}
    numbers["e2"] = {"arms": out, "notes_vs_engine": list(test), "teacher": kept, "rerun": bool(rerun), "first_run_cut": first_run}
    tables["e2-notes.md"] = table(
        "Table 5.11: Half B of the knowledge questions, with and without notes Claude left on half A",
        [2.6, 1.0, 1.0, 1.0], ["Set-up", "One fact", "Several facts", "All"], table_rows)


def trust(numbers, tables):
    rows = load("e3")
    if not rows:
        return
    out, table_rows = {}, []
    names = {"trust": "With the trust line", "no-trust": "Without it"}
    for arm in ["no-trust", "trust"]:
        nope = [r for r in rows if r["arm"] == arm and r["kind"] == "unanswerable"]
        yes = [r for r in rows if r["arm"] == arm and r["kind"] == "answerable"]
        item = {"declined_unanswerable": count(nope, "declined"), "right_answerable": count(yes),
                "wrongly_declined": (sum(1 for r in yes if r["declined"] and not r.get("right")), len(yes))}
        out[arm] = item
        table_rows.append([names[arm], of(item["declined_unanswerable"]), of(item["right_answerable"]), of(item["wrongly_declined"])])
    key = lambda r: (r["kind"], r["task"])
    by = {arm: {key(r): r for r in rows if r["arm"] == arm} for arm in ["trust", "no-trust"]}
    honest = [((by["trust"][k]["declined"] if k[0] == "unanswerable" else by["trust"][k].get("right")),
               (by["no-trust"][k]["declined"] if k[0] == "unanswerable" else by["no-trust"][k].get("right")))
              for k in by["trust"] if k in by["no-trust"]]
    numbers["e3"] = {"arms": out, "trust_vs_none": list(sign(honest))}
    tables["e3-trust.md"] = table(
        "Table 5.12: Qwen3 4B on 30 questions the vault cannot answer and 30 it can",
        [1.8, 1.4, 1.2, 1.2], ["Search results", "Said the vault does not hold it", "Answerable, right", "Answerable, wrongly declined"], table_rows)


def door(numbers, tables):
    rows = load("e4")
    if not rows:
        return
    out, table_rows = {}, []
    for model in [SMALL, LARGE]:
        for arm in ["door", "classic"]:
            mine = [r for r in rows if r["model"] == model and r["arm"] == arm]
            out[f"{model}:{arm}"] = {"right": count(mine), "looked_up": count(mine, "looked_up"), "bad_calls": sum(r["bad_calls"] for r in mine)}
        by = {arm: {r["task"]: r for r in rows if r["model"] == model and r["arm"] == arm} for arm in ["door", "classic"]}
        test = sign([(by["door"][t]["right"], by["classic"][t]["right"]) for t in by["door"] if t in by["classic"]])
        out[f"{model}:test"] = list(test)
        table_rows.append([NAMES[model], of(out[f"{model}:door"]["right"]), of(out[f"{model}:classic"]["right"]),
                           f"{test[0]} / {test[1]}", fmt_p(test[2])])
    numbers["e4"] = out
    tables["e4-door.md"] = table(
        "Table 5.13: Four tools against twelve, 16 knowledge questions per model",
        [1.4, 1.2, 1.2, 1.2, 0.8], ["Model", "Four tools, right", "Twelve tools, right", "Only four / only twelve right", "p (sign test)"], table_rows)


def chart(numbers):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = HERE / "figures" / "v3"
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 8.5, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
    ink, grid = "#1f2933", "#d5dbe1"
    fig, axes = plt.subplots(2, 2, figsize=(6.6, 5.2))

    def panel(ax, title, labels, values, colours, note=None, top=100):
        drawn = ax.bar(range(len(values)), values, 0.66, color=colours, edgecolor="white")
        for bar, value in zip(drawn, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + top * 0.015, f"{value:.0f}", ha="center", va="bottom", fontsize=7, color=ink)
        ax.set_xticks(range(len(values)), labels, fontsize=7)
        ax.set_ylim(0, top * 1.12)
        ax.set_title(title, fontsize=8.5, loc="left", color=ink)
        ax.yaxis.grid(True, color=grid, linewidth=0.6)
        ax.set_axisbelow(True)
        if note:
            ax.set_ylabel(note, fontsize=7.5)

    pct = lambda pair: 100 * pair[0] / pair[1] if pair[1] else 0
    grey, amber, blue, teal, navy = "#9aa5b1", "#e0861a", "#7b61c4", "#1a9e77", "#2f6fde"
    if "e1" in numbers:
        cells = numbers["e1"]["cells"]
        both = lambda arm: [cells[f"{SMALL}>{LARGE}:{arm}"]["right"], cells[f"{LARGE}>{SMALL}:{arm}"]["right"]]
        values = [pct((sum(p[0] for p in both(arm)), sum(p[1] for p in both(arm)))) for arm in ["fresh", "paste", "sessions", "ledger"]]
        panel(axes[0][0], "Carrying on a conversation", ["Nothing", "Transcript", "Sessions", "Ledger"], values, [grey, amber, blue, teal], "Answers right (%)")
    if "e2" in numbers:
        arms = numbers["e2"]["arms"]
        values = [pct(arms[a]["all"]) for a in ["alone", "engine", "engine+notes", "claude-alone"]]
        panel(axes[0][1], "Notes from a bigger model", ["4B alone", "4B + Burrow", "+ notes", "Claude alone"], values, [grey, blue, teal, navy])
    if "e3" in numbers:
        arms = numbers["e3"]["arms"]
        values = [pct(arms["no-trust"]["declined_unanswerable"]), pct(arms["trust"]["declined_unanswerable"]),
                  pct(arms["no-trust"]["right_answerable"]), pct(arms["trust"]["right_answerable"])]
        panel(axes[1][0], "Saying the vault does not hold it", ["Not held\nno line", "Not held\ntrust line", "Held\nno line", "Held\ntrust line"],
              values, [grey, teal, grey, teal], "Declined / right (%)")
    if "e4" in numbers:
        cells = numbers["e4"]
        values = [pct(cells[f"{SMALL}:classic"]["right"]), pct(cells[f"{SMALL}:door"]["right"]),
                  pct(cells[f"{LARGE}:classic"]["right"]), pct(cells[f"{LARGE}:door"]["right"])]
        panel(axes[1][1], "Four tools or twelve", ["4B\ntwelve", "4B\nfour", "12B\ntwelve", "12B\nfour"], values, [grey, teal, grey, teal])
    fig.tight_layout()
    fig.savefig(figures / "chart-eval3.png", dpi=220)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    numbers, tables = {}, {}
    meta = load("meta")
    numbers["meta"] = meta
    for step in (resume, notes, trust, door):
        step(numbers, tables)
    for name, text in tables.items():
        (OUT / name).write_text(text)
    (OUT / "numbers.json").write_text(json.dumps(numbers, indent=1))
    chart(numbers)
    print(json.dumps({k: v for k, v in numbers.items() if k != "meta"}, indent=1)[:4000])


if __name__ == "__main__":
    main()
