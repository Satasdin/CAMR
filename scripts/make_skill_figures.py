"""Figures for the skill-card experiment (docs/FINDINGS.md F32), drawn from results/skills/skill_cards.json.

    python scripts/make_skill_figures.py      # docs/figures/report/skill_cards.png
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("mrf", ROOT / "scripts/make_report_figures.py")
mrf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mrf)
plt, style, save = mrf.plt, mrf.style, mrf.save
BLUE, ORANGE, GREEN, GREY, INK2, SURF = mrf.BLUE, mrf.ORANGE, mrf.GREEN, mrf.GREY, mrf.INK2, mrf.SURF
PURPLE = "#7b4fd0"  # the skill cards: a fourth slot, apart from base (grey), notes (green) and merged LoRA (orange)
OUT = ROOT / "docs/figures/report"

CONDITIONS = [("base", "base model", GREY), ("memory", "memory notes", GREEN), ("merged", "one merged LoRA", ORANGE),
              ("card", "skill card, routed by memory", PURPLE)]


def skill_cards() -> Path:
    d = json.loads((ROOT / "results/skills/skill_cards.json").read_text())
    splits = [("test", "held-out"), ("rephrased", "reworded"), ("derived", "derived")]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.0, 4.2), facecolor=SURF, gridspec_kw={"width_ratios": [1.6, 1]})
    w = 0.2
    for i, (key, label, col) in enumerate(CONDITIONS):
        c = d["conditions"][key]
        xs = [k + (i - 1.5) * w for k in range(len(splits))]
        ys = [100 * c[s]["all"] for s, _ in splits]
        a1.bar(xs, ys, w, color=col, edgecolor=SURF, linewidth=1, label=label)
        for x, y in zip(xs, ys):
            a1.text(x, y + 1.2, f"{y:.0f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    a1.set_xticks(range(len(splits)), [n for _, n in splits])
    a1.set_ylim(0, 105)
    style(a1, ylabel="accuracy, %", grid="y")
    a1.set_title("Same 40 corrections: where the weights help")
    a1.legend(frameon=False, fontsize=8, loc="upper right")

    cl = d["control_large"]["conditions"]
    names = [("base", "base model", GREY), ("merged", "one merged\nLoRA", ORANGE), ("card", "skill cards,\nrouted", PURPLE)]
    for k, (key, label, col) in enumerate(names):
        v = cl[key]
        y, lo, hi = 100 * v["accuracy"], 100 * v["ci95"][0], 100 * v["ci95"][1]
        a2.bar(k, y, 0.6, color=col, edgecolor=SURF)
        a2.errorbar(k, y, yerr=[[y - lo], [hi - y]], color=INK2, capsize=4, linewidth=1)
        changed = v["lost_vs_base"] + v["gained_vs_base"]
        note = "" if key == "base" else f"\n{changed} answers changed"
        a2.text(k, hi + 0.8, f"{y:.1f}%{note}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    a2.set_xticks(range(len(names)), [n for _, n, _ in names])
    a2.set_ylim(0, 32)
    style(a2, ylabel=f"GSM8K accuracy, n = {d['control_large']['n']}, %", grid="y")
    a2.set_title("Unrelated problems: what the weights disturb")
    fig.tight_layout()
    return save(fig, OUT, "skill_cards.png")




# ---------------------------------------------------------------------- the readers and the link (Phases 5 and 3)
READER_LABEL = {"qwen2.5:0.5b": "qwen2.5 0.5B", "qwen2.5:1.5b": "qwen2.5 1.5B", "qwen2.5:3b": "qwen2.5 3B",
                "kimi-k3": "Kimi K3 (cloud)"}


def readers(tag: str = "baseline") -> Path:
    """Right alone and with memory, and what went wrong with memory, per reader (results/readers)."""
    recs = [json.loads(line) for line in (ROOT / f"results/readers/answers_{tag}.jsonl").read_text().splitlines()]
    names = [r for r in READER_LABEL if any(x["reader"] == r for x in recs)]
    fig, ax = plt.subplots(figsize=(10.0, 4.0), facecolor=SURF)
    w = 0.26
    for i, name in enumerate(names):
        rs = [x for x in recs if x["reader"] == name and x["correct"] is not None]
        alone = [x for x in rs if not x["memory"]]
        mem = [x for x in rs if x["memory"]]
        right_a = 100 * sum(x["correct"] for x in alone) / len(alone)
        right_m = 100 * sum(x["correct"] for x in mem) / len(mem)
        wrong_m = 100 * sum(1 for x in mem if not x["correct"] and not x["declined"]) / len(mem)
        for k, (y, col, lab) in enumerate([(right_a, GREY, "right, alone"), (right_m, GREEN, "right, with memory"),
                                            (wrong_m, ORANGE, "wrong stated, with memory")]):
            x = i + (k - 1) * w
            ax.bar(x, y, w, color=col, edgecolor=SURF, label=lab if i == 0 else None)
            ax.text(x, y + 1, f"{y:.0f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_xticks(range(len(names)), [READER_LABEL[n] for n in names])
    ax.set_ylim(0, 100)
    style(ax, ylabel="% of 287 questions", grid="y")
    ax.set_title("The same memory, read by models of every size")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    fig.tight_layout()
    return save(fig, OUT, "readers.png")


def link_tradeoff(tag: str = "baseline") -> Path:
    """Each reader's learned link at five prices for one cloud call: right answers (left) and wrong answers stated
    as fact (right) against the share of questions sent to the cloud model."""
    d = json.loads((ROOT / f"results/link/link_{tag}.json").read_text())
    cols = {"qwen2.5:0.5b": GREY, "qwen2.5:1.5b": BLUE, "qwen2.5:3b": PURPLE}
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), facecolor=SURF, sharex=True)
    esc = next(iter(d["readers"].values()))["fixed"]["always escalate"]
    for ax, key, ylab, title in ((axes[0], "right", "right answers, %", "Right answers: what sending questions away buys"),
                                 (axes[1], "wrong", "wrong answers stated as fact, %",
                                  "Wrong answers: what the link removes")):
        for name, r in d["readers"].items():
            pts = sorted(r["cloud_sweep"], key=lambda s: s["escalated"])
            ax.plot([100 * s["escalated"] for s in pts], [100 * s[key] for s in pts], "-o", color=cols.get(name, INK2),
                    label=f"{READER_LABEL.get(name, name)}, learned link", markersize=4.5, linewidth=1.6)
            ax.scatter([0], [100 * r["fixed"]["always keep"][key]], marker="x", s=55, color=cols.get(name, INK2),
                       zorder=3)
        ax.scatter([100], [100 * esc[key]], marker="s", s=40, color=GREEN, zorder=3, label="always ask Kimi K3")
        ax.set_xlim(-3, 104)
        ax.set_ylim(0, 85 if key == "right" else 55)
        style(ax, xlabel="questions sent to Kimi K3, %", ylabel=ylab, grid="both")
        ax.set_title(title)
    axes[1].annotate("× every answer kept", (2, 51), fontsize=7.5, color=INK2)
    axes[0].legend(frameon=False, fontsize=7.5, loc="lower right")
    fig.tight_layout()
    return save(fig, OUT, "link_tradeoff.png")

if __name__ == "__main__":
    skill_cards()
    if (ROOT / "results/readers/answers_baseline.jsonl").exists():
        readers()
    if (ROOT / "results/link/link_baseline.json").exists():
        link_tradeoff()
