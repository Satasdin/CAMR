"""Regenerate the findings figures from logged results (nothing typed by hand).

    python scripts/make_figures.py --pilot results/pilot --retrieval results/retrieval_eval --out docs/figures
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # validated categorical slots 1-3
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
METRIC = {"popqa": "contains", "hotpotqa": "em", "2wikimultihopqa": "em", "gsm8k": "accuracy"}
NAME = {"popqa": "PopQA (single-hop, long-tail)", "hotpotqa": "HotpotQA (multi-hop)", "gsm8k": "GSM8K (maths reasoning)",
        "2wikimultihopqa": "2WikiMultiHopQA (multi-hop)"}


def style(ax, ylabel: str) -> None:
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def acc(conn, label: str, cond: str, bench: str, first: bool = False) -> float | None:
    """Accuracy of the latest (or, with first=True, the earliest) completed run."""
    agg = "MIN" if first else "MAX"
    rid = conn.execute(f"SELECT {agg}(run_id) FROM run WHERE label=? AND condition=? AND benchmark=? AND status='completed'",
                       (label, cond, bench)).fetchone()[0]
    if rid is None:
        return None
    return conn.execute("SELECT AVG(s.value) FROM score s JOIN query_log q USING(query_id) WHERE q.run_id=? AND s.metric=?",
                        (rid, METRIC[bench])).fetchone()[0]


def fig_growth(pilot: Path, out: Path) -> Path | None:
    gpath = pilot / "tables" / "growth.json"
    if not gpath.exists():
        return None
    rows = json.loads(gpath.read_text())
    conn = sqlite3.connect(f"file:{pilot / 'camr.sqlite'}?mode=ro", uri=True)
    benches = [b for b in ("popqa", "hotpotqa", "gsm8k") if any(r["benchmark"] == b for r in rows)]
    fig, axes = plt.subplots(1, len(benches), figsize=(4.2 * len(benches), 3.9), sharey=True, facecolor=SURF)
    for ax, b in zip(axes, benches):
        # The growth stages' own session: the first floor/ceiling runs, measured just before the stages.
        pts = [(0.0, acc(conn, "main", "floor", b, first=True))] + [(r["corpus_share"], r["accuracy"]) for r in rows if r["benchmark"] == b]
        xs, ys = [p[0] * 100 for p in pts], [p[1] * 100 for p in pts]
        ax.plot(xs, ys, color=BLUE, linewidth=2, marker="o", markersize=6, zorder=3)
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8.5, color=INK)
        refs = [(n, ls, acc(conn, lab, "ceiling", b, first=(lab == "main"))) for lab, ls, n in
                (("main", "--", "gpt-oss-20b"), ("kimi", ":", "Kimi K3 (cloud)"))]
        refs = [r for r in refs if r[2] is not None]
        for name, ls, v in refs:
            ax.axhline(v * 100, color=INK2, linestyle=ls, linewidth=1.2)
        if len(refs) == 2 and abs(refs[0][2] - refs[1][2]) < 0.06:  # coincident lines: one shared label
            ax.text(101, refs[0][2] * 100, f"20B & Kimi {refs[0][2] * 100:.0f}%", va="center", fontsize=8, color=INK2)
        else:
            for name, ls, v in refs:
                ax.text(101, v * 100, f"{name} {v * 100:.0f}%", va="center", fontsize=8, color=INK2)
        ax.set_title(NAME[b], fontsize=10, color=INK, loc="left")
        ax.set_xticks([0, 25, 50, 100])
        ax.set_xticklabels(["empty", "25%", "50%", "100%"])
        ax.set_xlabel("share of knowledge corpus in the store", color=INK2, fontsize=9)
        ax.set_ylim(0, 105)
        style(ax, "accuracy (%)" if ax is axes[0] else "")
    fig.suptitle("A frozen 0.5B model gains as its memory grows: on long-tail facts it reaches Kimi K3's score",
                 fontsize=11.5, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, "Qwen2.5-0.5B (blue) with CAMR; reference lines = large models without memory. "
             "Pilot: 30 / 30 / 12 questions, CPU-only laptop-class machine.", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 0.93, 0.95))
    p = out / "fig_growth_accuracy.png"
    fig.savefig(p, dpi=170, facecolor=SURF)
    plt.close(fig)
    return p


def fig_speed(pilot: Path, out: Path) -> Path | None:
    gpath = pilot / "tables" / "growth.json"
    if not gpath.exists():
        return None
    rows = json.loads(gpath.read_text())
    conn = sqlite3.connect(f"file:{pilot / 'camr.sqlite'}?mode=ro", uri=True)
    fig, ax = plt.subplots(figsize=(7.6, 3.8), facecolor=SURF)
    for b, col in (("popqa", BLUE), ("hotpotqa", ORANGE), ("gsm8k", AQUA)):
        rid = conn.execute("SELECT MAX(run_id) FROM run WHERE label='main' AND condition='floor' AND benchmark=?", (b,)).fetchone()[0]
        v = [g / (d / 1000) for g, d in conn.execute("SELECT generated_tokens, decode_ms FROM query_log WHERE run_id=?", (rid,)) if g and d]
        v.sort()
        floor_speed = v[len(v) // 2] if v else None
        pts = [(0, floor_speed)] + [(r["corpus_share"] * 100, r["median_decode_tok_per_s"]) for r in rows if r["benchmark"] == b]
        xs, ys = zip(*[p for p in pts if p[1] is not None])
        ax.plot(xs, ys, color=col, linewidth=2, marker="o", markersize=6)
        ax.text(102, ys[-1], NAME[b].split(" (")[0], va="center", fontsize=8.5, color=INK)
    ax.set_ylim(0, 70)
    ax.set_xlim(-3, 118)
    ax.set_xticks([0, 25, 50, 100])
    ax.set_xticklabels(["no memory", "25%", "50%", "100%"])
    ax.set_xlabel("share of knowledge corpus in the store", color=INK2, fontsize=9)
    style(ax, "decode speed (tokens/s, median)")
    ax.set_title("Decode speed stays flat as the memory store grows", fontsize=11, color=INK, loc="left")
    fig.text(0.01, 0.01, "Qwen2.5-0.5B on 4 CPU cores; speeds from the Ollama runtime's own timers (eval_count / eval_duration).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    p = out / "fig_decode_speed.png"
    fig.savefig(p, dpi=170, facecolor=SURF)
    plt.close(fig)
    return p


def fig_retrieval(reval: Path, out: Path) -> Path | None:
    """Difference from the similarity-only baseline (pp), and tokens actually supplied, per budget."""
    jpath = reval / "tables" / "retrieval_eval.json"
    if not jpath.exists():
        return None
    rows = json.loads(jpath.read_text())["rows"]
    out_paths = []
    for b in sorted({r["benchmark"] for r in rows}):
        by = {(r["label"].split("@")[0], r["budget"]): r for r in rows if r["benchmark"] == b}
        budgets = sorted({bud for (lab, bud) in by if lab == "control"})
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.9), facecolor=SURF)
        w = 0.36
        series = (("bridged-ungated", ORANGE, "+ entity bridging"), ("bridged-sim", BLUE, "+ gating + bridging"))
        for i, (lab, col, name) in enumerate(series):
            xs, ys = [], []
            for j, bud in enumerate(budgets):
                if (lab, bud) in by:
                    xs.append(j + (i - 0.5) * w)
                    ys.append((by[(lab, bud)]["support_all"] - by[("control", bud)]["support_all"]) * 100)
            ax1.bar(xs, ys, width=w - 0.04, color=col, label=name)
            for x, y in zip(xs, ys):
                ax1.text(x, y + (0.4 if y >= 0 else -0.4), f"{y:+.1f}", ha="center", va="bottom" if y >= 0 else "top",
                         fontsize=7.5, color=INK)
        ax1.axhline(0, color=INK2, linewidth=1)
        ax1.set_xticks(range(len(budgets)))
        ax1.set_xticklabels([str(x) for x in budgets])
        ax1.set_xlabel("token budget (ceiling)", color=INK2, fontsize=9)
        style(ax1, "change in full-support recall vs baseline (pp)")
        ax1.legend(frameon=False, fontsize=8, loc="lower right")
        ax1.set_title("Recall: bridging helps at 1024, costs at 256", fontsize=10, color=INK, loc="left")
        for i, (lab, col, name) in enumerate((("control", INK2, "baseline"), ("bridged-sim", BLUE, "+ gating + bridging"))):
            xs = [j + (i - 0.5) * w for j, bud in enumerate(budgets) if (lab, bud) in by]
            ys = [by[(lab, bud)]["mean_context_tokens"] for bud in budgets if (lab, bud) in by]
            ax2.bar(xs, ys, width=w - 0.04, color=col, label=name)
        ax2.set_xticks(range(len(budgets)))
        ax2.set_xticklabels([str(x) for x in budgets])
        ax2.set_xlabel("token budget (ceiling)", color=INK2, fontsize=9)
        style(ax2, "tokens actually supplied (mean)")
        ax2.legend(frameon=False, fontsize=8, loc="upper left")
        ax2.set_title("Cost: gating sends up to 28% fewer tokens", fontsize=10, color=INK, loc="left")
        n = next(r["n"] for r in rows if r["benchmark"] == b)
        fig.suptitle(f"{NAME.get(b, b)}: retrieval quality and cost against the similarity-only baseline (n={n})",
                     fontsize=11, color=INK, x=0.01, ha="left")
        fig.text(0.01, 0.005, "Full-support recall = both gold supporting paragraphs admitted to the context. "
                 "BGE-small; ~24k verbatim notes from real Wikipedia paragraphs.", fontsize=7.5, color=INK2)
        fig.tight_layout(rect=(0, 0.03, 1, 0.93))
        p = out / f"fig_retrieval_{b}.png"
        fig.savefig(p, dpi=170, facecolor=SURF)
        plt.close(fig)
        out_paths.append(p)
    return out_paths[0] if out_paths else None


def _params(meta_path: Path) -> dict[str, float]:
    meta = json.loads(meta_path.read_text())
    out = {}
    for m, d in meta.items():
        v = d["parameter_size"]
        out[m] = float(v[:-1]) / (1000 if v.endswith("M") else 1)
    return out


def fig_model_sweep(pilot: Path, out: Path, meta_path: Path) -> Path | None:
    """Accuracy without -> with memory against parameter count, per task type (one dot pair per model)."""
    jpath = pilot / "tables" / "model_sweep.json"
    if not jpath.exists() or not meta_path.exists():
        return None
    rows = [r for r in json.loads(jpath.read_text()) if r["floor"] is not None]
    params = _params(meta_path)
    benches = [b for b in ("popqa", "hotpotqa", "gsm8k") if any(r["benchmark"] == b for r in rows)]
    fig, axes = plt.subplots(1, len(benches), figsize=(4.4 * len(benches), 4.1), sharey=True, facecolor=SURF, squeeze=False)
    for ax, b in zip(axes[0], benches):
        rs = sorted((r for r in rows if r["benchmark"] == b and r["model"] in params), key=lambda r: params[r["model"]])
        # Models of near-equal size are nudged apart (multiplicatively, so log spacing stays honest).
        xs, last = {}, None
        for r in rs:
            x = params[r["model"]]
            if last is not None and x / last < 1.12:
                x = last * 1.12
            xs[r["model"]] = last = x
        for r in rs:
            x = xs[r["model"]]
            f, m = r["floor"] * 100, r["with_memory"] * 100
            col = BLUE if m > f else ORANGE if m < f else INK2
            if m != f:
                ax.annotate("", xy=(x, m), xytext=(x, f),
                            arrowprops=dict(arrowstyle="-|>", color=col, lw=1.4, shrinkA=3, shrinkB=3))
                ax.scatter([x], [f], s=22, color=INK2, zorder=3)
            ax.scatter([x], [m], s=30, color=col, zorder=4, edgecolors=SURF if m == f else "none", linewidths=1)
        refs = [(name, ls, next((r[lab] for r in rs if r.get(lab) is not None), None))
                for lab, ls, name in (("ceiling_20b", "--", "gpt-oss-20b"), ("ceiling_kimi", ":", "Kimi K3"))]
        refs = [x for x in refs if x[2] is not None]
        for name, ls, v in refs:
            ax.axhline(v * 100, color=INK2, linestyle=ls, linewidth=1.1)
        if len(refs) == 2 and abs(refs[0][2] - refs[1][2]) < 0.06:
            ax.text(16.5, refs[0][2] * 100 - 4, "20B & Kimi K3", va="center", fontsize=7.5, color=INK2)
        else:
            for name, ls, v in refs:
                ax.text(16.5, v * 100 + 2.5, name, va="center", fontsize=7.5, color=INK2)
        ax.set_xscale("log")
        ax.set_xticks([0.5, 1, 2, 4, 8, 15])
        ax.set_xticklabels(["0.5B", "1B", "2B", "4B", "8B", "15B"])
        ax.set_xlim(0.4, 30)
        ax.set_ylim(0, 105)
        ax.set_xlabel("parameters (log scale)", color=INK2, fontsize=9)
        ax.set_title(NAME[b], fontsize=10, color=INK, loc="left")
        style(ax, "accuracy (%)" if ax is axes[0][0] else "")
    fig.suptitle("Where the engine helps: accuracy without (grey) and with CAMR memory, by model size",
                 fontsize=11.5, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, "Each arrow is one model: grey dot = alone, arrow head = with CAMR (blue helps, orange hurts, grey no change). Parameter counts from the Ollama "
             "registry; 30 / 30 / 12 questions; same store and questions for every model.", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    p = out / "fig_model_sweep.png"
    fig.savefig(p, dpi=170, facecolor=SURF)
    plt.close(fig)
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", default="results/pilot")
    ap.add_argument("--retrieval", default="results/retrieval_eval")
    ap.add_argument("--out", default="docs/figures")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (fig_growth(Path(a.pilot), out), fig_speed(Path(a.pilot), out), fig_retrieval(Path(a.retrieval), out),
              fig_model_sweep(Path(a.pilot), out, Path("docs/model_registry_metadata.json"))):
        print(f)


if __name__ == "__main__":
    main()
