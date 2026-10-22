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


def _reader_shares(tag: str) -> dict[str, dict[str, float]]:
    """Per reader on one read path: right alone, right with memory, wrong stated with memory (% of its questions)."""
    p = ROOT / f"results/readers/answers_{tag}.jsonl"
    if not p.exists():
        return {}
    recs = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    out = {}
    for name in READER_LABEL:
        rs = [x for x in recs if x["reader"] == name and x["correct"] is not None]
        alone, mem = [x for x in rs if not x["memory"]], [x for x in rs if x["memory"]]
        if alone and mem:
            out[name] = {"alone": 100 * sum(x["correct"] for x in alone) / len(alone),
                         "memory": 100 * sum(x["correct"] for x in mem) / len(mem),
                         "wrong": 100 * sum(1 for x in mem if not x["correct"] and not x["declined"]) / len(mem)}
    return out


def readers(tag: str = "phase2b", before: str = "baseline", reversed_: str = "phase2") -> Path:
    """Right alone and with memory before Phase 2 and now (the compressed read path as a marker), and wrong answers
    stated with memory now, per reader (results/readers)."""
    now, old, comp = _reader_shares(tag), _reader_shares(before), _reader_shares(reversed_)
    names = [n for n in READER_LABEL if n in now]
    fig, ax = plt.subplots(figsize=(10.4, 4.3), facecolor=SURF)
    w = 0.2
    bars = [("alone", now, GREY, "right, alone"), ("memory", old, "#9cc3ee", "right with memory, before Phase 2"),
            ("memory", now, BLUE, "right with memory, now"), ("wrong", now, ORANGE, "wrong stated with memory, now")]
    for i, name in enumerate(names):
        for k, (key, src, col, lab) in enumerate(bars):
            if name not in src:
                continue
            x, y = i + (k - 1.5) * w, src[name][key]
            ax.bar(x, y, w, color=col, edgecolor=SURF, label=lab if i == 0 else None)
            top = max(y, comp[name]["memory"] + 1) if k == 2 and name in comp else y  # clear the compressed marker
            ax.text(x, top + 1, f"{y:.0f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
        if name in comp:
            ax.scatter([i + 0.5 * w], [comp[name]["memory"]], marker="_", s=260, color=INK2, linewidths=1.8, zorder=4,
                       label="right with memory, compressed (reversed)" if i == 0 else None)
    ax.set_xticks(range(len(names)), [READER_LABEL[n] for n in names])
    ax.set_ylim(0, 100)
    style(ax, ylabel="% of 287 questions", grid="y")
    ax.set_title("The same memory, read by models of every size")
    ax.legend(frameon=False, fontsize=7.5, ncol=3, loc="upper left")
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

BENCH_TARGETS = {"A3": 0.85, "A4": 0.70, "A6": 0.85, "A7": 0.50}  # the Phase 2 targets (results/bench/phase2/README.md)


def engine_bench() -> Path:
    """Answer reached the model, per ability: before Phase 2, with compression (reversed, D-41) and CAMR Personal
    now, scored with the answer-survives rule (the cards scripts/phase2_compare.py prints; the 1M store, built on the
    baseline only, left out)."""
    spec = importlib.util.spec_from_file_location("phase2_compare", ROOT / "scripts/phase2_compare.py")
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    from camr.eval.abilities import scorecard
    cards = {}
    for name, files, _ in pc.HEADLINE:
        rs = [json.loads(x) for f in files if f.exists() for x in f.read_text().splitlines() if x.strip()]
        cards[name] = scorecard(r for r in rs if not str(r.get("suite", "")).endswith("-1M"))
    before, comp, now = cards["baseline"], cards["phase2-compressed"], cards["phase2b"]
    abil = sorted(before, key=lambda a: int(a[1:]), reverse=True)
    fig, ax = plt.subplots(figsize=(9.6, 5.2), facecolor=SURF)
    for k, a in enumerate(abil):
        b, n = 100 * before[a]["pass_rate"], 100 * now[a]["pass_rate"]
        ax.plot([b, n], [k, k], color=GREY, linewidth=1.2, zorder=1)
        lo, hi = (100 * v for v in now[a]["ci95"])
        ax.plot([lo, hi], [k - 0.18, k - 0.18], color=BLUE, linewidth=0.8, alpha=0.6)
        if a in BENCH_TARGETS:
            ax.plot([100 * BENCH_TARGETS[a]] * 2, [k - 0.32, k + 0.32], color="black", linewidth=1.6)
    ys = list(range(len(abil)))
    ax.scatter([100 * before[a]["pass_rate"] for a in abil], ys, s=42, color=GREY, zorder=3, label="before Phase 2")
    ax.scatter([100 * comp[a]["pass_rate"] for a in abil], ys, s=46, marker="x", color=ORANGE, zorder=3,
               label="with compression (reversed)")
    ax.scatter([100 * now[a]["pass_rate"] for a in abil], ys, s=52, color=BLUE, zorder=4,
               label="CAMR Personal now (95% interval below)")
    ax.plot([], [], color="black", linewidth=1.6, label="target")
    ax.set_yticks(ys, [f"{a} {before[a]['name']} (n={before[a]['n']})" for a in abil])
    ax.set_xlim(0, 101)
    style(ax, xlabel="questions whose answer reached the model, %", grid="x")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.1), ncol=2, fontsize=8, frameon=False)
    ax.set_title("Engine bench: what reached the model, before and after Phase 2", loc="left")
    fig.tight_layout()
    return save(fig, OUT, "engine_bench.png")


if __name__ == "__main__":
    skill_cards()
    if (ROOT / "results/bench/phase2/phase2b").exists():
        engine_bench()
    if (ROOT / "results/readers/answers_phase2b.jsonl").exists():
        readers()
    for tag in ("phase2b", "baseline"):
        if (ROOT / f"results/link/link_{tag}.json").exists():
            link_tradeoff(tag)
            break
