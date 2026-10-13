"""Figures for the learning extensions of Chapter 5 (eager learning, external weights, sleep), from logged results.

    python scripts/make_learning_figures.py --out docs/figures/report
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mrf", HERE / "make_report_figures.py")
mrf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mrf)
plt, style, save = mrf.plt, mrf.style, mrf.save
BLUE, ORANGE, GREEN, GREY, INK, INK2, GRID, SURF = mrf.BLUE, mrf.ORANGE, mrf.GREEN, mrf.GREY, mrf.INK, mrf.INK2, mrf.GRID, mrf.SURF
ROOT = HERE.parent
EAGER = ROOT / "results/eager"
# closed-book baselines: one grey ramp, darker = larger model (identity by label, not colour alone)
BASELINES = [("qwen2.5_0.5b", "0.5B alone", "#b7bdc8"), ("qwen2.5_1.5b", "1.5B alone", "#949cab"),
             ("llama3.2_3b", "3B alone", "#6f7888"), ("gpt-oss_20b", "20B alone", "#3f4654")]


def _load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def fig_learning_curve(out: Path) -> Path | None:
    learn = _load(EAGER / "learn.json")
    if not learn:
        return None
    turns = sorted(learn["turns"], key=lambda t: t["i"])
    x = np.arange(1, len(turns) + 1)
    start = 10  # a running accuracy over the first few questions is noise
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.8, 3.9), facecolor=SURF, gridspec_kw={"width_ratios": [1.7, 1]})
    labels = []
    for key, label, col in BASELINES:
        b = _load(EAGER / f"baseline_{key}.json")
        if not b or len(b["per_question"]) < len(turns):
            continue
        c = np.cumsum([q["correct"] for q in sorted(b["per_question"], key=lambda q: q["i"])][: len(turns)]) / x
        ax.plot(x[start:], 100 * c[start:], color=col, lw=1.8)
        labels.append([100 * c[-1], f"{label} {100 * c[-1]:.1f}%", INK2, "normal"])
    c = np.cumsum([t["correct"] for t in turns]) / x
    ax.plot(x[start:], 100 * c[start:], color=GREEN, lw=2.4)
    labels.append([100 * c[-1], f"0.5B + eager learning {100 * c[-1]:.1f}%", GREEN, "bold"])
    labels.sort(key=lambda r: r[0])
    for k in range(1, len(labels)):  # keep end labels at least 3.6 points apart
        labels[k][0] = max(labels[k][0], labels[k - 1][0] + 3.6)
    for yv, text, col, weight in labels:
        ax.text(len(turns) + 3, yv, text, color=col, fontsize=7.8, va="center", fontweight=weight)
    ax.set_xlim(0, len(turns) * 1.55)
    ax.set_ylim(0, max(60, 100 * c[start:].max() + 8))
    style(ax, xlabel="questions seen (in stream order)", ylabel="accuracy so far (%)")
    ax.set_title("A frozen 0.5B model that looks up what it doesn't know", loc="left")
    notes = [t["notes_total"] for t in turns]
    from_mem = np.cumsum([t["memory_had_it"] for t in turns])
    ax2.plot(x, notes, color=BLUE, lw=2.0)
    ax2.text(len(turns), notes[-1], f" {notes[-1]} notes\n {turns[-1]['store_bytes'] / 1e6:.1f} MB", color=BLUE,
             fontsize=8, va="center")
    ax2.set_xlim(0, len(turns) * 1.3)
    style(ax2, xlabel="questions seen", ylabel="notes in memory")
    ax2.set_title(f"Memory grows; {from_mem[-1]} answers needed no lookup", loc="left")
    return save(fig, out, "learning_curve.png")


def fig_compete(out: Path) -> Path | None:
    """Accuracy against the model process's resident memory: closed-book models vs a small model with memory."""
    learn, retain, ram = _load(EAGER / "learn.json"), _load(EAGER / "retain.json"), _load(EAGER / "ram.json")
    if not learn:
        return None
    rss = {m: v["rss_mb"] / 1024 for m, v in (ram or {}).get("models", {}).items()}
    pts = []
    for key, label, col in BASELINES:
        b = _load(EAGER / f"baseline_{key}.json")
        model = key.replace("_", ":", 1) if not key.startswith("gpt") else "gpt-oss:20b"
        if b and "accuracy" in b and (model in rss or b.get("peak_model_rss_mb")):
            pts.append((rss.get(model, (b.get("peak_model_rss_mb") or 0) / 1024), 100 * b["accuracy"], label, col, "o"))
    mem_gb = rss.get("qwen2.5:0.5b", (learn.get("peak_model_rss_mb") or 0) / 1024)
    acc = 100 * np.mean([t["correct"] for t in learn["turns"]])
    pts.append((mem_gb, acc, "0.5B + eager learning (online)", GREEN, "D"))
    if retain:
        for model, lab in (("qwen2.5:0.5b", "0.5B + learned memory, offline,\nreworded"),
                           ("llama3.2:3b", "3B + the same memory, offline,\nreworded")):
            if model in retain["models"]:
                pts.append((rss.get(model, retain["models"][model]["peak_model_rss_mb"] / 1024),
                            100 * retain["models"][model]["accuracy"], lab, BLUE, "s"))
    fig, ax = plt.subplots(figsize=(8.2, 4.6), facecolor=SURF)
    offsets = {"0.5B + eager learning (online)": (9, 8), "0.5B + learned memory, offline,\nreworded": (9, -22),
               "20B alone": (-58, 8)}
    for gx, gy, label, col, mk in pts:
        ax.scatter([gx], [gy], s=70, color=col, marker=mk, edgecolor=SURF, linewidth=1.5, zorder=3)
        ax.annotate(label, (gx, gy), xytext=offsets.get(label, (7, 4)), textcoords="offset points", fontsize=7.8,
                    color=INK2)
    ax.set_xscale("log")
    ax.set_xlim(0.5, 20)
    ax.set_xticks([0.5, 1, 2, 4, 8, 16])
    ax.set_xticklabels(["0.5", "1", "2", "4", "8", "16"])
    ax.minorticks_off()
    ax.set_ylim(0, max(p[1] for p in pts) + 12)
    style(ax, xlabel="resident memory of the model process (GB, log scale)", ylabel="accuracy (%)")
    ax.set_title("Knowledge from memory, not from size: accuracy against RAM", loc="left")
    return save(fig, out, "compete_ram.png")


def fig_token_memory(out: Path) -> Path | None:
    tm, ft = _load(ROOT / "results/token_memory/test.json"), _load(ROOT / "results/finetune/test.json")
    if not tm:
        return None
    rows = [("0.5B alone", tm["conditions"]["base"]["accuracy"], GREY)]
    if ft:
        sel = ft["conditions"].get("lora") or next((v for k, v in ft["conditions"].items() if "lora" in k.lower()), None)
        if sel:
            acc = sel.get("test_closed", sel).get("accuracy")
            if acc is not None:
                rows.append(("Inside: LoRA", acc, ORANGE))
    rows += [("Beside: kNN-LM", tm["conditions"]["knn_lm"]["accuracy"], "#8a63d2"),
             ("In the prompt: CAMR", tm["conditions"]["camr"]["accuracy"], GREEN),
             ("kNN-LM + CAMR", tm["conditions"]["knn_lm+camr"]["accuracy"], BLUE)]
    fig, ax = plt.subplots(figsize=(7.4, 3.3), facecolor=SURF)
    for y, (label, acc, col) in enumerate(rows):
        ax.barh(y, 100 * acc, color=col, height=0.62, edgecolor=SURF)
        ax.text(100 * acc + 1, y, f"{100 * acc:.1f}%", va="center", fontsize=8, color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    style(ax, xlabel="held-out PopQA accuracy (n = 60), same documents, same runtime")
    ax.set_title("Where the frozen model's knowledge lives", loc="left")
    return save(fig, out, "token_memory.png")


def fig_index_scaling(out: Path) -> Path | None:
    idx = _load(ROOT / "results/sleep/index.json")
    if not idx or not idx.get("scale"):
        return None
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.0, 3.6), facecolor=SURF)
    for mode, col, label in (("exact", ORANGE, "exact search"), ("ivf", GREEN, "learned index (IVF)")):
        r = sorted([s for s in idx["scale"] if s["mode"] == mode], key=lambda s: s["notes"])
        n = [s["notes"] / 1000 for s in r]
        ax.plot(n, [s["ms"] for s in r], color=col, lw=2, marker="o", ms=5)
        ax.text(n[-1], r[-1]["ms"], f"  {label}", color=col, fontsize=8, va="center")
        ax2.plot(n, [s["rss_mb_after_queries"] for s in r], color=col, lw=2, marker="o", ms=5)
        ax2.text(n[-1], r[-1]["rss_mb_after_queries"], f"  {label}", color=col, fontsize=8, va="center")
    ax.set_xlim(0, max(s["notes"] for s in idx["scale"]) / 1000 * 1.45)
    ax2.set_xlim(0, max(s["notes"] for s in idx["scale"]) / 1000 * 1.45)
    style(ax, xlabel="notes in memory (thousands)", ylabel="ms per question (median)")
    style(ax2, xlabel="notes in memory (thousands)", ylabel="process memory after 1,000 questions (MB)")
    ax.set_title("Search time as memory grows", loc="left")
    ax2.set_title("Resident memory as memory grows", loc="left")
    return save(fig, out, "index_scaling.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs/figures/report"))
    out = Path(ap.parse_args().out)
    for f in (fig_learning_curve, fig_compete, fig_token_memory, fig_index_scaling):
        p = f(out)
        print(f.__name__, p)
