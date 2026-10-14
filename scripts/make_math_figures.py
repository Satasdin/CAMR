"""Figures for learning formulas from corrections, computed from results/math (nothing typed by hand).

    python scripts/make_math_figures.py --out docs/figures/report
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("mrf", ROOT / "scripts/make_report_figures.py")
mrf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mrf)
plt, style, save = mrf.plt, mrf.style, mrf.save
BLUE, ORANGE, GREEN, GREY, INK2, SURF = mrf.BLUE, mrf.ORANGE, mrf.GREEN, mrf.GREY, mrf.INK2, mrf.SURF
MATH = ROOT / "results/math"
LABEL = {"qwen2.5_0.5b_calc": "Qwen 0.5B, writes the expression", "qwen2.5_0.5b_reason": "Qwen 0.5B, works it out",
         "kimi-k3_calc": "Kimi K3, writes the expression"}
COLOR = {"qwen2.5_0.5b_calc": BLUE, "qwen2.5_0.5b_reason": ORANGE, "kimi-k3_calc": GREEN}


def runs() -> dict[str, dict]:
    out = {}
    for f in sorted(MATH.glob("run_*.json")):
        key = f.stem[4:]
        if key in LABEL:
            out[key] = json.loads(f.read_text())
    return out


def fig_curve(out: Path) -> Path | None:
    """Held-out accuracy as corrections accumulate, and where it ends on seen, unseen, reworded and derived problems."""
    rs = runs()
    if not rs:
        return None
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.2, 4.0), facecolor=SURF, gridspec_kw={"width_ratios": [1.1, 1]})
    for key, d in rs.items():
        xs = [c["round"] for c in d["curve"]]
        ys = [100 * c["test"]["all"] for c in d["curve"]]
        a1.plot(xs, ys, color=COLOR[key], linewidth=2, marker="o", markersize=5, label=f"{LABEL[key]}: all")
        inv = [100 * c["test"]["invented"] for c in d["curve"]]
        a1.plot(xs, inv, color=COLOR[key], linewidth=1.4, linestyle="--", marker="s", markersize=4,
                label=f"{LABEL[key]}: invented formulas")
        a1.annotate(f"{ys[-1]:.0f}%", (xs[-1], ys[-1]), xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=8, color=INK2)
    a1.set_ylim(0, 105)
    a1.set_xticks(sorted({c["round"] for d in rs.values() for c in d["curve"]}))
    style(a1, xlabel="training rounds (one problem per formula per round; corrected only when wrong)",
          ylabel="held-out accuracy, %", grid="y")
    a1.set_title("Held-out accuracy as corrections accumulate", loc="left")
    a1.legend(frameon=False, fontsize=7.5, loc="lower right")
    splits = [("train", "seen\n(corrected)"), ("test", "unseen"), ("rephrased", "unseen,\nreworded"),
              ("derived", "derived\n(inverted, nested)")]
    w = 0.8 / len(rs)
    for i, (key, d) in enumerate(rs.items()):
        xs = [j + (i - (len(rs) - 1) / 2) * w for j in range(len(splits))]
        vals = [100 * d["after"][s]["all"] for s, _ in splits]
        a2.bar(xs, vals, width=w - 0.03, color=COLOR[key], edgecolor=SURF, linewidth=1, label=LABEL[key])
        for x, v in zip(xs, vals):
            a2.text(x, v + 1.5, f"{v:.0f}", ha="center", fontsize=7, color=INK2)
    a2.set_xticks(range(len(splits)), [n for _, n in splits])
    a2.set_ylim(0, 105)
    style(a2, ylabel="accuracy after learning, %", grid="y")
    a2.set_title("After learning: seen vs unseen problems", loc="left")
    a2.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    fig.tight_layout()
    return save(fig, out, "math_learning_curve.png")


def fig_lora(out: Path) -> Path | None:
    """Fine-tuning epoch by epoch (training vs validation vs held-out) against memory, same model and runtime."""
    p = MATH / "lora_vs_memory.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    curve = d.get("lora_curve", [])
    if not curve:
        return None
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.2, 4.0), facecolor=SURF, gridspec_kw={"width_ratios": [1.1, 1]})
    ep = [c["epoch"] for c in curve]
    for s, col, name in (("train", ORANGE, "LoRA: training problems"), ("val", GREY, "LoRA: validation"),
                         ("test", BLUE, "LoRA: held-out")):
        a1.plot(ep, [100 * c[s] for c in curve], color=col, linewidth=2, marker="o", markersize=5, label=name)
    mem = d["conditions"].get("memory")
    if mem:
        a1.axhline(100 * mem["test"]["all"], color=GREEN, linewidth=2, linestyle="--",
                   label=f"memory: held-out ({100 * mem['test']['all']:.0f}%)")
    a1.set_ylim(0, 100)
    a1.set_xticks(ep)
    style(a1, xlabel="LoRA epochs", ylabel="accuracy, %", grid="y")
    a1.set_title("Fine-tuning: training vs new problems per epoch", loc="left")
    a1.legend(frameon=False, fontsize=8, loc="upper left")
    conds = list(d["conditions"])
    splits = [("train", "seen"), ("test", "unseen"), ("rephrased", "reworded"), ("derived", "derived"),
              ("gsm8k", "GSM8K")]
    cols = [GREY, GREEN, BLUE, ORANGE]
    w = 0.8 / len(conds)
    for i, name in enumerate(conds):
        v = d["conditions"][name]
        xs = [j + (i - (len(conds) - 1) / 2) * w for j in range(len(splits))]
        vals = [100 * v[s]["all"] for s, _ in splits]
        a2.bar(xs, vals, width=w - 0.03, color=cols[i % len(cols)], edgecolor=SURF, linewidth=1, label=name)
        for x, val in zip(xs, vals):
            a2.text(x, val + 1.5, f"{val:.0f}", ha="center", fontsize=6.5, color=INK2)
    a2.set_xticks(range(len(splits)), [n for _, n in splits])
    a2.set_ylim(0, 105)
    style(a2, ylabel="accuracy, %", grid="y")
    a2.set_title("Same corrections: memory vs fine-tuning", loc="left")
    a2.legend(frameon=False, fontsize=7.5, loc="upper right")
    fig.tight_layout()
    return save(fig, out, "math_lora_vs_memory.png")



def fig_ablation(out: Path, model: str = "qwen2.5_0.5b_calc") -> Path | None:
    """Which part of a correction carries the learning: one correction per formula, stored as the worked example
    alone, the rule alone, or both; against no correction at all."""
    ab, run = MATH / f"ablate_{model}.json", MATH / f"run_{model}.json"
    if not ab.exists() or not run.exists():
        return None
    a, r = json.loads(ab.read_text()), json.loads(run.read_text())
    conds = [("no correction", r["before"], GREY), ("worked example only", a["variants"]["worked example only"], ORANGE),
             ("rule only", a["variants"]["rule only"], BLUE),
             ("rule + worked example", a["variants"]["rule + worked example"], GREEN)]
    splits = [("test", "new problems"), ("rephrased", "reworded"), ("derived", "derived (inverted, nested)")]
    fig, ax = plt.subplots(figsize=(8.4, 3.8), facecolor=SURF)
    w = 0.8 / len(conds)
    for i, (name, v, col) in enumerate(conds):
        xs = [j + (i - (len(conds) - 1) / 2) * w for j in range(len(splits))]
        vals = [100 * v[s]["all"] for s, _ in splits]
        ax.bar(xs, vals, width=w - 0.03, color=col, edgecolor=SURF, linewidth=1, label=name)
        for x, val in zip(xs, vals):
            ax.text(x, val + 1.2, f"{val:.0f}", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(range(len(splits)), [n for _, n in splits])
    ax.set_ylim(0, 70)
    style(ax, ylabel="accuracy, %", grid="y")
    ax.set_title(f"{LABEL.get(model, model)}: one correction per formula, stored three ways", loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    return save(fig, out, "math_ablation.png")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/figures/report")
    o = Path(ap.parse_args().out)
    o.mkdir(parents=True, exist_ok=True)
    fig_curve(o)
    fig_ablation(o)
    fig_lora(o)
