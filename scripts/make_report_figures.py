"""Extra report figures for Chapters 5 and 6, all computed from the logged results (nothing typed by hand).

    python scripts/make_report_figures.py --out docs/figures/report
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BLUE, ORANGE, GREEN = "#2a78d6", "#eb6834", "#1baf7a"   # validated categorical slots 1-3
GREY, INK, INK2, GRID, SURF = "#9aa3b2", "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "results" / "pilot"
METRIC = {"popqa": "contains", "hotpotqa": "em", "gsm8k": "accuracy"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold"})


def style(ax, xlabel=None, ylabel=None, grid="x"):
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.grid(axis=grid, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8.5)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2)


def save(fig, out: Path, name: str) -> Path:
    p = out / name
    fig.savefig(p, dpi=180, bbox_inches="tight", facecolor=SURF)
    plt.close(fig)
    print(p)
    return p


def sweep() -> dict[str, dict]:
    rows = json.loads((PILOT / "tables" / "model_sweep.json").read_text())
    meta = json.loads((ROOT / "docs" / "model_registry_metadata.json").read_text())
    by: dict[str, dict] = {}
    for r in rows:
        by.setdefault(r["model"], {"model": r["model"], "params": meta.get(r["model"], {}).get("parameter_size", "?")})[r["benchmark"]] = r
    return by


def latency() -> dict[str, float]:
    c = sqlite3.connect(f"file:{PILOT / 'camr.sqlite'}?mode=ro", uri=True)
    q = ("SELECT r.label, AVG(q.e2e_latency_ms)/1000 FROM run r JOIN query_log q USING(run_id) WHERE r.condition='treatment' "
         "AND r.benchmark='popqa' AND r.label LIKE 'm:%' AND q.status='ok' AND r.run_id IN (SELECT MAX(run_id) FROM run "
         "WHERE status='completed' GROUP BY label, condition, benchmark) GROUP BY r.label")
    return {k[2:]: v for k, v in c.execute(q)}


# ------------------------------------------------------------------ rankings
def fig_rank(out: Path, memory: bool) -> Path:
    by = sweep()
    key = "with_memory" if memory else "floor"
    mean = {m: np.mean([d[b][key] for b in METRIC if b in d]) for m, d in by.items()}
    models = sorted(by, key=lambda m: mean[m])
    fig, ax = plt.subplots(figsize=(7.4, 6.2), facecolor=SURF)
    y = np.arange(len(models))
    ax.barh(y, [100 * mean[m] for m in models], color="#e9f1fb", edgecolor="none", height=0.72, label="mean of the three")
    for b, col, mk in (("popqa", BLUE, "o"), ("hotpotqa", ORANGE, "s"), ("gsm8k", GREEN, "^")):
        ax.scatter([100 * by[m][b][key] for m in models], y, color=col, marker=mk, s=26, zorder=3,
                   label={"popqa": "PopQA (facts)", "hotpotqa": "HotpotQA (multi-hop)", "gsm8k": "GSM8K (maths)"}[b])
    def ps(p):
        return f"{float(p[:-1]) / 1000:.1f}B" if p.endswith("M") else p
    ax.set_yticks(y, [f"{m}  ({ps(by[m]['params'])})" for m in models], fontsize=8)
    for i, m in enumerate(models):
        ax.text(100 * mean[m] + 1, i, f"{100 * mean[m]:.0f}", va="center", fontsize=7.5, color=INK2)
    kimi = {"popqa": 66.7, "hotpotqa": 53.3}
    for b, col in (("popqa", BLUE), ("hotpotqa", ORANGE)):
        ax.axvline(kimi[b], color=col, linestyle=":", linewidth=1)
    ax.text(66.7, -1.6, "Kimi K3\nfacts", color=BLUE, fontsize=7, ha="center", va="top")
    ax.text(53.3, -1.6, "Kimi K3\nmulti-hop", color=ORANGE, fontsize=7, ha="center", va="top")
    ax.set_ylim(-2.8, len(models) - 0.4)
    ax.set_xlim(0, 100)
    style(ax, "accuracy (%)")
    ax.set_title(("With CAMR memory" if memory else "Small models alone (no memory)") + ": ranked by mean accuracy", loc="left")
    ax.legend(loc="lower right", fontsize=7.5, frameon=False)
    return save(fig, out, f"rank_{'with_camr' if memory else 'alone'}.png")


def fig_gain(out: Path) -> Path:
    by = sweep()
    models = sorted(by, key=lambda m: by[m]["popqa"]["with_memory"] - by[m]["popqa"]["floor"])
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 5.6), sharey=True, facecolor=SURF)
    for ax, b in zip(axes, METRIC):
        g = [100 * (by[m][b]["with_memory"] - by[m][b]["floor"]) for m in models]
        ax.barh(range(len(models)), g, color=[BLUE if v > 0 else GREY if v == 0 else ORANGE for v in g], height=0.7)
        ax.axvline(0, color=INK2, linewidth=0.8)
        ax.set_title({"popqa": "PopQA gain", "hotpotqa": "HotpotQA gain", "gsm8k": "GSM8K change (exemplars)"}[b], loc="left")
        style(ax, "points")
    axes[0].set_yticks(range(len(models)), models, fontsize=8)
    fig.suptitle("What memory adds, per model (percentage points; blue = helps, orange = hurts)", x=0.01, ha="left",
                 fontsize=10, fontweight="bold")
    return save(fig, out, "gain_per_model.png")


def fig_speed_accuracy(out: Path) -> Path:
    by, lat = sweep(), latency()
    fig, ax = plt.subplots(figsize=(7.4, 4.6), facecolor=SURF)
    for m, d in by.items():
        if m not in lat:
            continue
        x, yv = lat[m], 100 * d["popqa"]["with_memory"]
        ax.scatter(x, yv, color=BLUE, s=34, zorder=3)
        ax.annotate(m, (x, yv), textcoords="offset points", xytext=(4, 3), fontsize=7, color=INK2)
    ax.scatter([7.7], [66.7], color=ORANGE, marker="D", s=46, zorder=3)
    ax.annotate("Kimi K3 (cloud, no memory)", (7.7, 66.7), textcoords="offset points", xytext=(6, -10), fontsize=7.5, color=ORANGE)
    ax.axvspan(0, 7.7, color=GREEN, alpha=0.06)
    ax.text(0.4, 83, "faster than the cloud model", color=GREEN, fontsize=8)
    ax.set_xscale("log")
    ax.set_xticks([1, 2, 4, 8, 16], ["1 s", "2 s", "4 s", "8 s", "16 s"])
    ax.set_ylim(55, 85)
    style(ax, "mean seconds per answer with CAMR (4-core CPU, log scale)", "PopQA accuracy with CAMR (%)", grid="both")
    ax.set_title("Speed vs accuracy on long-tail facts: 1.5–4B models beat the cloud on both", loc="left")
    return save(fig, out, "speed_vs_accuracy.png")


# ------------------------------------------------------------------ n = 200
def fig_hotpot200(out: Path) -> Path | None:
    db = ROOT / "results" / "hotpot200" / "camr.sqlite"
    if not db.exists():
        return None
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = ("SELECT r.label, r.condition, q.question_id, s.value FROM run r JOIN query_log q USING(run_id) JOIN score s USING(query_id) "
         "WHERE s.metric='em' AND q.status='ok' AND r.status='completed' AND r.run_id IN (SELECT MAX(run_id) FROM run "
         "WHERE status='completed' GROUP BY label, condition, benchmark)")
    d: dict = {}
    for label, cond, qid, v in c.execute(q):
        d.setdefault(label, {}).setdefault(cond, {})[qid] = v
    rows = [("qwen2.5:0.5b", "m:qwen2.5:0.5b", "floor", "treatment"), ("qwen2.5:1.5b", "m:qwen2.5:1.5b", "floor", "treatment"),
            ("llama3.2:3b", "m:llama3.2:3b", "floor", "treatment"), ("Kimi K3 (cloud)", "kimi", "ceiling", "ceiling_rag")]
    rng = random.Random(13)

    def ci(vals):
        bs = sorted(np.mean([rng.choice(vals) for _ in vals]) for _ in range(2000))
        return bs[50], bs[1949]

    fig, ax = plt.subplots(figsize=(7.4, 4.0), facecolor=SURF)
    for i, (name, lab, a, b) in enumerate(rows):
        A, B = d[lab][a], d[lab][b]
        ids = sorted(set(A) & set(B))
        for j, (vals, col, txt) in enumerate(((([A[k] for k in ids]), GREY, "alone"), (([B[k] for k in ids]), BLUE if lab != "kimi" else ORANGE, "with CAMR"))):
            m = np.mean(vals)
            lo, hi = ci(vals)
            x = i + (j - 0.5) * 0.36
            ax.bar(x, 100 * m, width=0.34, color=col, edgecolor="none")
            ax.errorbar(x, 100 * m, yerr=[[100 * (m - lo)], [100 * (hi - m)]], color=INK2, capsize=3, linewidth=1)
            ax.text(x, 100 * hi + 1.5, f"{100 * m:.1f}", ha="center", fontsize=7.5, color=INK2)
    ax.axhline(100 * np.mean(list(d["kimi"]["ceiling"].values())), color=ORANGE, linestyle=":", linewidth=1)
    ax.set_xticks(range(len(rows)), [r[0] for r in rows])
    ax.set_ylim(0, 80)
    style(ax, None, "exact match (%), 95% CI", grid="y")
    ax.set_title("HotpotQA, 200 held-out questions: alone (grey) vs with the same notes", loc="left")
    return save(fig, out, "hotpot200.png")


# ------------------------------------------------------------------ pilot analyses
def acc(conn, label, cond, bench):
    rid = conn.execute("SELECT MAX(run_id) FROM run WHERE label=? AND condition=? AND benchmark=? AND status='completed'",
                       (label, cond, bench)).fetchone()[0]
    if rid is None:
        return None
    return conn.execute("SELECT AVG(s.value) FROM score s JOIN query_log q USING(query_id) WHERE q.run_id=? AND s.metric=?",
                        (rid, METRIC[bench])).fetchone()[0]


def fig_budget(out: Path) -> Path:
    c = sqlite3.connect(f"file:{PILOT / 'camr.sqlite'}?mode=ro", uri=True)
    budgets = [0, 128, 512, 1024]
    fig, ax = plt.subplots(figsize=(6.6, 3.8), facecolor=SURF)
    for b, col, mk, name in (("popqa", BLUE, "o", "single-hop facts (PopQA)"), ("hotpotqa", ORANGE, "s", "multi-hop (HotpotQA)"),
                             ("gsm8k", GREEN, "^", "maths (GSM8K)")):
        ys = [100 * (acc(c, f"budget-{x:04d}", "treatment", b) or 0) for x in budgets]
        ax.plot(range(len(budgets)), ys, color=col, marker=mk, linewidth=2, markersize=6, label=name)
        best = int(np.argmax(ys))
        ax.annotate(f"{ys[best]:.1f}", (best, ys[best]), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8, color=col)
    ax.set_xticks(range(len(budgets)), [f"{x} tokens" for x in budgets])
    style(ax, "memory budget per question", "accuracy (%), qwen2.5:0.5b", grid="y")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("More memory is not better for a tiny model: 128 tokens wins on facts", loc="left")
    return save(fig, out, "budget_curve.png")


def fig_funnel(out: Path) -> Path:
    rows = {}
    for line in (PILOT / "tables" / "coverage.md").read_text().splitlines():
        p = [x.strip() for x in line.strip("|").split("|")]
        if len(p) > 8 and p[0] == "main":
            rows[p[1]] = [float(v) for v in p[4:8]]
    stages = ["answer in store", "in retrieved\ncandidates", "in context\nsent to model", "answered\ncorrectly"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6), sharey=True, facecolor=SURF)
    for ax, (b, name) in zip(axes, (("popqa", "PopQA (single-hop)"), ("hotpotqa", "HotpotQA (multi-hop)"))):
        v = [100 * x for x in rows[b]]
        cols = [BLUE, BLUE, BLUE, GREEN]
        ax.bar(range(4), v, color=cols, width=0.62)
        for i, x in enumerate(v):
            ax.text(i, x + 1.5, f"{x:.0f}%", ha="center", fontsize=8.5, color=INK2)
        ax.set_xticks(range(4), stages, fontsize=8)
        ax.set_ylim(0, 110)
        style(ax, None, "share of questions (%)" if b == "popqa" else None, grid="y")
        ax.set_title(name, loc="left")
    fig.suptitle("Where answers are lost (0.5B + CAMR, pilot): retrieval delivers; the small model's reading is the bottleneck",
                 x=0.01, ha="left", fontsize=10, fontweight="bold")
    return save(fig, out, "error_funnel.png")


def fig_residual(out: Path) -> Path:
    names = ["single-hop\n(PopQA)", "multi-hop\n(HotpotQA)", "maths\n(GSM8K)"]
    small = [66.7, 30.0, 16.7]
    big = [76.7, 53.3, 100.0]
    fig, ax = plt.subplots(figsize=(6.6, 3.6), facecolor=SURF)
    x = np.arange(3)
    ax.bar(x - 0.18, small, width=0.34, color=BLUE, label="0.5B + CAMR")
    ax.bar(x + 0.18, big, width=0.34, color=ORANGE, label="gpt-oss-20b + same notes")
    for i in range(3):
        ax.annotate("", xy=(i + 0.18, big[i]), xytext=(i + 0.18, small[i]), arrowprops=dict(arrowstyle="<->", color=INK2, lw=1))
        ax.text(i + 0.38, (big[i] + small[i]) / 2, f"{big[i] - small[i]:.1f} pts", fontsize=8, color=INK2, va="center")
    ax.set_xticks(x, names)
    ax.set_ylim(0, 110)
    style(ax, None, "accuracy (%)", grid="y")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Residual gap: what model size still buys when both read the same notes", loc="left")
    return save(fig, out, "residual_gap.png")


def fig_gating(out: Path) -> Path | None:
    files = [(ROOT / "docs" / "calibration" / f"gating_{n}_values.json", t) for n, t in (("bge", "BGE-small (benchmarks)"),
                                                                                        ("nomic", "nomic-embed-text (app)"))]
    files = [(f, t) for f, t in files if f.exists()]
    if not files:
        return None
    fig, axes = plt.subplots(1, len(files), figsize=(4.9 * len(files), 3.4), facecolor=SURF)
    axes = np.atleast_1d(axes)
    for ax, (f, title) in zip(axes, files):
        d = json.loads(f.read_text())
        bins = np.linspace(0.2, 1.0, 41)
        ax.hist(d["irrelevant_values"], bins=bins, color=ORANGE, alpha=0.75, label="off-topic memory")
        ax.hist(d["relevant_values"], bins=bins, color=BLUE, alpha=0.75, label="relevant memory")
        thr = d["min_similarity_same_rule_as_benchmarks"]
        ax.axvline(thr, color=INK, linewidth=1.2, linestyle="--")
        ax.text(thr + 0.01, ax.get_ylim()[1] * 0.9, f"abstain below {thr:.2f}", fontsize=8)
        style(ax, "cosine similarity to the question", "questions", grid="y")
        ax.set_title(title, loc="left")
        ax.legend(frameon=False, fontsize=7.5, loc="upper left")
    fig.suptitle("Gating calibration on 200 HotpotQA questions: one rule (90th percentile of off-topic) for every embedder",
                 x=0.01, ha="left", fontsize=10, fontweight="bold")
    return save(fig, out, "gating_calibration.png")


def fig_timeline(out: Path) -> Path:
    log = subprocess.run(["git", "log", "--reverse", "--format=%ad|%s", "--date=format:%Y-%m-%d %H:%M"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip().splitlines()
    import datetime as dt

    pts = sorted((dt.datetime.strptime(line.split("|", 1)[0], "%Y-%m-%d %H:%M"), line.split("|", 1)[1]) for line in log
                 if not line.split("|", 1)[1].startswith("Merge"))
    phases = [("engine built from the proposal", "Build the CAMR"), ("capability-adaptive + residual gap", "capability-adaptive"),
              ("real-model pilot", "real-model pilot"), ("memory growth", "memory-growth"), ("model sweep across machines", "model-size sweep"),
              ("cloud ceiling (Kimi)", "OpenAI-compatible"), ("learned policy", "Learn the engine"), ("pilot findings", "full pilot results"),
              ("grounding cascade", "Grounding cascade"), ("setup guide + app v0.1", "Setup walkthrough"), ("19-model sweep + 2Wiki", "machine D merged"),
              ("app 0.2: UI + downloads", "CAMR Personal 0.2"), ("n = 200 confirmation", "F13"), ("release workflow", "Release workflow")]
    marks = []
    for name, key in phases:
        hit = next((t for t, s in pts if key in s), None)
        if hit:
            marks.append((hit, name))
    first = pts[0][0]
    day = pts[-1][0].date()
    pts = [(t, m) for t, m in pts if t.date() == day]
    marks = [(t, n) for t, n in marks if t.date() == day]
    fig, ax = plt.subplots(figsize=(9.6, 4.6), facecolor=SURF)
    hrs = [t.hour + t.minute / 60 for t, _ in pts]
    ax.plot(hrs, range(1, len(hrs) + 1), color=BLUE, linewidth=1.8, drawstyle="steps-post")
    for t, name in marks:
        k = next(i for i, (tt, _) in enumerate(pts) if tt == t) + 1
        h = t.hour + t.minute / 60
        ax.scatter(h, k, color=ORANGE, s=18, zorder=3)
        ax.annotate(name, (h, k), textcoords="offset points", xytext=(-8, 4), ha="right", fontsize=7, color=INK2, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.set_xticks(range(int(min(hrs)), int(max(hrs)) + 2), [f"{h:02d}:00" for h in range(int(min(hrs)), int(max(hrs)) + 2)])
    style(ax, f"time of day, {day:%d %b %Y} (the engine was first built on {first:%d %b}, from the proposal)",
          f"commits on {day:%d %b} (cumulative)", grid="both")
    ax.set_title("Development process from the git history: each step is a commit with its measured result", loc="left")
    return save(fig, out, "timeline.png")


def fig_app_latency(out: Path) -> Path | None:
    """What a CAMR Personal user waits for: time to the first word, cold vs after warm-up vs a typical answer."""
    src = ROOT / "docs" / "results" / "app_latency.json"
    if not src.exists():
        return None
    d = json.loads(src.read_text())
    models = list(d["models"])
    series = [("First answer after a reboot (weights read from disk)", lambda m: m["cold_disk"]["first_token_ms"], ORANGE),
              ("First answer, model not loaded (weights in OS cache)", lambda m: m["cold"]["first_token_ms"], GREY),
              ("First answer after warm-up (app default)", lambda m: m["after_warm"]["first_token_ms"], BLUE),
              ("Typical answer, median (384-token budget)", lambda m: m["budgets"]["384"]["median_first_token_ms"], GREEN)]
    fig, ax = plt.subplots(figsize=(7.6, 4.4), facecolor=SURF)
    h = 0.2
    for i, (label, get, col) in enumerate(series):
        ys = [j + (i - 1.5) * h for j in range(len(models))]
        vals = [get(d["models"][m]) / 1000 for m in models]
        ax.barh(ys, vals, height=h - 0.04, color=col, label=label, edgecolor=SURF, linewidth=1)
        for y, v in zip(ys, vals):
            ax.text(v * 1.08, y, f"{v:.1f} s", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(range(len(models)), models)
    ax.invert_yaxis()
    ax.set_xscale("log")
    style(ax, xlabel="seconds until the first word appears (log scale; 4-core CPU, no GPU)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("CAMR Personal: time to first word, cold vs warmed", loc="left")
    return save(fig, out, "app_latency.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/figures/report")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (lambda: fig_rank(out, False), lambda: fig_rank(out, True), lambda: fig_gain(out), lambda: fig_speed_accuracy(out),
              lambda: fig_hotpot200(out), lambda: fig_budget(out), lambda: fig_funnel(out), lambda: fig_residual(out),
              lambda: fig_gating(out), lambda: fig_timeline(out), lambda: fig_app_latency(out)):
        f()
