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


if __name__ == "__main__":
    skill_cards()
