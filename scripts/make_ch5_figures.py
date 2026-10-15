"""Figures for the rewritten Chapter 5: RAG pipelines, model choice, automations and agents, costs.

Every bar is read from a results file; a figure whose files are missing is skipped.

    python scripts/make_ch5_figures.py --out docs/figures/report
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
RED = "#c8443c"
RB = ROOT / "results/ragbench"
AG = ROOT / "results/agentic"
PIPE_LABEL = {"dense": "Naive RAG (dense)", "bm25": "BM25", "hybrid": "Hybrid (RRF)", "rerank": "Hybrid + reranker",
              "hyde": "HyDE", "crag": "Corrective RAG", "abstain": "Reranker + abstain", "check": "Reranker + CAMR check",
              "camr": "CAMR (verified)"}
ORDER = list(PIPE_LABEL)
READERS = [("qwen2.5:0.5b", "qwen2.5 0.5B"), ("llama3.2:3b", "llama3.2 3B"), ("kimi-k3", "Kimi K3 (cloud)")]


def rag_runs() -> dict[tuple[str, str], dict]:
    out = {}
    for f in RB.glob("run_*.json"):
        d = json.loads(f.read_text())
        out[(d["reader"], d["pipeline"])] = d
    return out


def summ(d: dict) -> dict:
    return d.get("summary_judged") or d["summary"]


def fig_rag_outcomes(out: Path) -> Path | None:
    runs = rag_runs()
    readers = [(r, n) for r, n in READERS if any((r, p) in runs for p in ORDER)]
    if not readers:
        return None
    fig, axes = plt.subplots(1, len(readers), figsize=(4.2 * len(readers) + 1.2, 4.4), facecolor=SURF, sharey=True)
    axes = [axes] if len(readers) == 1 else list(axes)
    pipes = [p for p in ORDER if any((r, p) in runs for r, _ in readers)]
    ys = list(range(len(pipes)))[::-1]
    for ax, (reader, name) in zip(axes, readers):
        for y, p in zip(ys, pipes):
            if (reader, p) not in runs:
                ax.text(1, y, "not run", va="center", fontsize=7, color=INK2)
                continue
            s = summ(runs[(reader, p)])
            c, w, d = 100 * s["correct_exact"], 100 * s["wrong_exact"], 100 * s["declined"]
            ax.barh(y, c, color=GREEN, edgecolor=SURF, linewidth=1.5, height=0.7)
            ax.barh(y, w, left=c, color=ORANGE, edgecolor=SURF, linewidth=1.5, height=0.7)
            ax.barh(y, d, left=c + w, color=GREY, edgecolor=SURF, linewidth=1.5, height=0.7)
            ax.text(c / 2, y, f"{c:.0f}", ha="center", va="center", fontsize=7.5, color="white")
            if w >= 6:
                ax.text(c + w / 2, y, f"{w:.0f}", ha="center", va="center", fontsize=7.5, color="white")
        ax.set_yticks(ys, [PIPE_LABEL[p] for p in pipes])
        ax.set_xlim(0, 100)
        style(ax, xlabel="% of 200 held-out questions", grid="x")
        ax.set_title(name, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREEN, ORANGE, GREY)]
    fig.legend(handles, ["correct", "wrong, stated as fact", "declined / not confirmed"], frameon=False, fontsize=8.5,
               loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("Modern RAG pipelines and CAMR: same corpus, same reader, same questions", x=0.01, ha="left",
                 fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    return save(fig, out, "rag_outcomes.png")


def fig_rag_tradeoff(out: Path) -> Path | None:
    runs = rag_runs()
    if not runs:
        return None
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.6, 4.4), facecolor=SURF)
    marks = dict(zip(ORDER, "osDv^<>Pp*"))
    for (reader, name), col in zip(READERS, (BLUE, ORANGE, GREEN)):
        for p in ORDER:
            d = runs.get((reader, p))
            if not d:
                continue
            s = summ(d)
            a1.scatter(100 * s["wrong_exact"], 100 * s["correct_exact"], color=col, marker=marks[p], s=46,
                       edgecolor=SURF, linewidth=1, zorder=3)
            a2.scatter(max(s["model_s"], 0.05), 100 * s["correct_exact"], color=col, marker=marks[p], s=46,
                       edgecolor=SURF, linewidth=1, zorder=3)
            if p == "camr":
                a1.annotate("CAMR", (100 * s["wrong_exact"], 100 * s["correct_exact"]), xytext=(5, 4),
                            textcoords="offset points", fontsize=7.5, color=INK2)
    style(a1, xlabel="wrong answers stated as fact, %", ylabel="correct, %", grid="both")
    a1.set_title("Accuracy against hallucination (up and left is better)", loc="left")
    a2.set_xscale("log")
    style(a2, xlabel="model seconds per question (log; 4-core CPU or cloud)", ylabel="correct, %", grid="both")
    a2.set_title("Accuracy against time", loc="left")
    rh = [plt.Line2D([], [], color=c, marker="o", linestyle="", markersize=7) for c in (BLUE, ORANGE, GREEN)]
    ph = [plt.Line2D([], [], color=INK2, marker=marks[p], linestyle="", markersize=6) for p in ORDER]
    fig.legend(rh + ph, [n for _, n in READERS] + [PIPE_LABEL[p] for p in ORDER], frameon=False, fontsize=7.5,
               loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    return save(fig, out, "rag_tradeoff.png")


def fig_rag_cost(out: Path) -> Path | None:
    runs = rag_runs()
    base = [p for p in ORDER if ("qwen2.5:0.5b", p) in runs]
    if not base:
        return None
    s = {p: summ(runs[("qwen2.5:0.5b", p)]) for p in base}
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.0), facecolor=SURF, sharey=True)
    ys = list(range(len(base)))[::-1]
    panels = [("gold_in_context", 100, "answer in what was read, %", BLUE),
              ("prompt_tokens", 1, "prompt tokens per question", ORANGE),
              ("cpu_ms", 1, "retrieval CPU, ms per question", GREY)]
    for ax, (k, mul, label, col) in zip(axes, panels):
        vals = [mul * s[p][k] for p in base]
        ax.barh(ys, vals, color=col, edgecolor=SURF, linewidth=1.5, height=0.65)
        for y, v in zip(ys, vals):
            ax.text(v, y, f" {v:.0f}", va="center", fontsize=7.5, color=INK2)
        style(ax, xlabel=label, grid="x")
    axes[0].set_yticks(ys, [PIPE_LABEL[p] for p in base])
    fig.suptitle("What each pipeline reads and what it costs to read it (0.5B reader)", x=0.01, ha="left",
                 fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return save(fig, out, "rag_cost.png")


def fig_models(out: Path) -> Path | None:
    models = [("qwen2.5:0.5b", "", "0.5B"), ("qwen2.5:1.5b", "_sa_qwen2_5_1_5b", "1.5B"),
              ("llama3.2:3b", "_sa_llama3_2_3b", "3B"), ("phi4-mini", "_sa_phi4-mini", "phi4-mini 3.8B"),
              ("qwen2.5:7b", "_sa_qwen2_5_7b", "7B")]
    judged = ROOT / "results/verified/judged_heldout.json"
    jd = json.loads(judged.read_text())["files"] if judged.exists() else {}
    speed = ROOT / "results/models/speed.json"
    sp = json.loads(speed.read_text())["models"] if speed.exists() else {}
    rows = []
    for m, tag, name in models:
        f = ROOT / f"results/verified/answers_heldout{tag or '_sa'}.json"
        if not f.exists():
            continue
        key = f.name
        v = jd.get(key, {}).get("facts+compress+reader", {}).get("verified")
        if v is None:
            d = json.loads(f.read_text())["variants"]["facts+compress+reader"]["verified"]
            v = {"correct": d["correct"], "hallucinated": d["wrong_unambiguous"], "other_meaning": d["wrong_other_meaning"]}
        rows.append((name, v, sp.get(m, {})))
    if not rows:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 3.9), facecolor=SURF)
    xs = range(len(rows))
    axes[0].bar([x - 0.2 for x in xs], [100 * r[1]["correct"] for r in rows], width=0.38, color=GREEN, label="correct")
    axes[0].bar([x + 0.2 for x in xs], [100 * r[1]["hallucinated"] for r in rows], width=0.38, color=ORANGE,
                label="hallucinated")
    for x, r in zip(xs, rows):
        axes[0].text(x - 0.2, 100 * r[1]["correct"] + 1, f"{100 * r[1]['correct']:.1f}", ha="center", fontsize=7)
        axes[0].text(x + 0.2, 100 * r[1]["hallucinated"] + 1, f"{100 * r[1]['hallucinated']:.1f}", ha="center",
                     fontsize=7)
    axes[0].set_xticks(list(xs), [r[0] for r in rows], fontsize=8)
    style(axes[0], ylabel="% of 200 held-out questions", grid="y")
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].set_title("Verified pipeline, reader swapped", loc="left")
    for ax, key, label, col in ((axes[1], "s_per_answer_median", "seconds per answer (median)", BLUE),
                                (axes[2], "rss_mb", "model memory, MB", GREY)):
        vals = [r[2].get(key) or 0 for r in rows]
        ax.bar(list(xs), vals, color=col, width=0.6)
        for x, v in zip(xs, vals):
            ax.text(x, v, f"{v:.1f}" if v < 100 else f"{v:.0f}", ha="center", va="bottom", fontsize=7)
        ax.set_xticks(list(xs), [r[0] for r in rows], fontsize=8)
        style(ax, ylabel=label, grid="y")
    axes[1].set_title("Speed on a 4-core CPU", loc="left")
    axes[2].set_title("Memory", loc="left")
    fig.tight_layout()
    return save(fig, out, "model_choice.png")


def _desk_rows():
    names = [("llm_qwen2_5_0_5b", "0.5B alone"), ("llm_llama3_2_3b", "3B alone"),
             ("stuff_llama3_2_3b", "3B + whole KB in prompt"),
             ("rag_llama3_2_3b", "3B + modern RAG"), ("camr_qwen2_5_0_5b", "0.5B + CAMR"),
             ("camr_llama3_2_3b", "3B + CAMR"), ("llm_kimi-k3", "Kimi alone"),
             ("stuff_kimi-k3", "Kimi + whole KB in prompt"), ("rag_kimi-k3", "Kimi + modern RAG"),
             ("camr_kimi-k3", "Kimi + CAMR")]
    out = []
    for tag, name in names:
        f = AG / f"helio_{tag}.json"
        if f.exists():
            out.append((name, json.loads(f.read_text())["summary"]))
    return out


def fig_desk(out: Path) -> Path | None:
    rows = _desk_rows()
    if not rows:
        return None
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.0, 4.6), facecolor=SURF, gridspec_kw={"width_ratios": [2.2, 1]})
    ys = list(range(len(rows)))[::-1]
    for y, (name, s) in zip(ys, rows):
        n = s["tickets"]
        kinds = s["by_kind"]
        correct = 100 * s["auto_resolved_correct"]
        wrong = 100 * sum(k["wrong"] for k in kinds.values()) / n
        stale = 100 * sum(k["stale"] for k in kinds.values()) / n
        esc = 100 - correct - wrong - stale
        left = 0
        for v, col in ((correct, GREEN), (wrong, ORANGE), (stale, RED), (esc, GREY)):
            a1.barh(y, v, left=left, color=col, edgecolor=SURF, linewidth=1.5, height=0.7)
            if v >= 7:
                a1.text(left + v / 2, y, f"{v:.0f}", ha="center", va="center", fontsize=7.5, color="white")
            left += v
        a2.barh(y, s["cost_usd_per_1000_tickets"], color=BLUE, height=0.6)
        a2.text(s["cost_usd_per_1000_tickets"], y, f" ${s['cost_usd_per_1000_tickets']:.2f}", va="center",
                fontsize=7.5, color=INK2)
    a1.set_yticks(ys, [r[0] for r in rows])
    a1.set_xlim(0, 100)
    style(a1, xlabel="% of 60 tickets", grid="x")
    a1.set_title("n8n support desk: what reached the customer", loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREEN, ORANGE, RED, GREY)]
    a1.legend(handles, ["correct reply", "wrong reply", "stale (superseded policy)", "handed to a person"],
              frameon=False, fontsize=7.5, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.24))
    a2.set_yticks(ys, [])
    style(a2, xlabel="cloud cost, USD per 1,000 tickets", grid="x")
    a2.set_title("Cost", loc="left")
    fig.tight_layout()
    return save(fig, out, "agentic_desk.png")


def fig_agent(out: Path) -> Path | None:
    cfgs = [("llama3_2_3b__none", "3B, no memory"), ("llama3_2_3b__rag", "3B + RAG memory"),
            ("llama3_2_3b__camr", "3B + CAMR memory"), ("kimi-k3__none", "Kimi, no memory"),
            ("kimi-k3__rag", "Kimi + RAG memory"), ("kimi-k3__camr", "Kimi + CAMR memory")]
    rows = [(n, json.loads((AG / f"agent_{t}.json").read_text())["summary"]) for t, n in cfgs
            if (AG / f"agent_{t}.json").exists()]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(9.6, 3.9), facecolor=SURF)
    xs = range(len(rows))
    ax.bar([x - 0.2 for x in xs], [100 * s["success"] for _, s in rows], width=0.38, color=GREEN,
           label="task completed correctly")
    ax.bar([x + 0.2 for x in xs], [100 * s["hallucinated_actions"] for _, s in rows], width=0.38, color=ORANGE,
           label="hallucinated action (wrong invoice or reply)")
    for x, (_, s) in zip(xs, rows):
        ax.text(x - 0.2, 100 * s["success"] + 1, f"{100 * s['success']:.0f}", ha="center", fontsize=7.5)
        ax.text(x + 0.2, 100 * s["hallucinated_actions"] + 1, f"{100 * s['hallucinated_actions']:.0f}", ha="center",
                fontsize=7.5)
    ax.set_xticks(list(xs), [n for n, _ in rows], fontsize=8)
    ax.set_ylim(0, 110)
    style(ax, ylabel="% of 20 tasks", grid="y")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Operations agent (n8n): invoices, replies and escalations on 20 tasks", loc="left")
    fig.tight_layout()
    return save(fig, out, "agentic_agent.png")


def fig_fresh(out: Path) -> Path | None:
    names = [("llm_llama3_2_3b", "3B alone"), ("rag_llama3_2_3b", "3B + modern RAG"),
             ("camr_llama3_2_3b", "3B + CAMR"), ("llm_kimi-k3", "Kimi alone"),
             ("stuff_kimi-k3", "Kimi + all 30 days in prompt"), ("rag_kimi-k3", "Kimi + modern RAG"),
             ("camr_kimi-k3", "Kimi + CAMR")]
    rows = [(n, json.loads((AG / f"fresh_{t}.json").read_text())["summary"]) for t, n in names
            if (AG / f"fresh_{t}.json").exists()]
    if not rows:
        return None
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.6, 4.0), facecolor=SURF, gridspec_kw={"width_ratios": [2.2, 1]})
    ys = list(range(len(rows)))[::-1]
    for y, (name, s) in zip(ys, rows):
        left = 0
        for v, col in ((100 * s["correct"], GREEN), (100 * s["wrong_stated"], ORANGE), (100 * s["declined"], GREY)):
            a1.barh(y, v, left=left, color=col, edgecolor=SURF, linewidth=1.5, height=0.7)
            if v >= 7:
                a1.text(left + v / 2, y, f"{v:.0f}", ha="center", va="center", fontsize=7.5, color="white")
            left += v
        a2.barh(y, s["cost_usd_per_1000_questions"], color=BLUE, height=0.6)
        a2.text(s["cost_usd_per_1000_questions"], y, f" ${s['cost_usd_per_1000_questions']:.2f}", va="center",
                fontsize=7.5, color=INK2)
    a1.set_yticks(ys, [r[0] for r in rows])
    a1.set_xlim(0, 100)
    style(a1, xlabel="% of 50 questions about news from the last 30 days", grid="x")
    a1.set_title("Real data: Wikipedia current events, fetched live by n8n", loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREEN, ORANGE, GREY)]
    a1.legend(handles, ["correct", "wrong, stated as fact", "declined"], frameon=False, fontsize=7.5,
              loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.24))
    a2.set_yticks(ys, [])
    style(a2, xlabel="cloud cost, USD per 1,000 questions", grid="x")
    a2.set_title("Cost", loc="left")
    fig.tight_layout()
    return save(fig, out, "agentic_fresh.png")


def fig_costs(out: Path) -> Path | None:
    p = ROOT / "results/costs/kimi_costs.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    agg: dict[str, float] = {}
    for r in d["rows"]:
        key = r["what"].split(":")[0]
        label = {"F9 pilot": "Pilot (F9)", "F13": "HotpotQA n=200 (F13)", "F19/F22": "Learning (F19, F22)",
                 "F24": "Verified answers + judge (F24)", "F27": "Learning formulas (F27)",
                 "F28": "RAG pipelines (F28)", "F29": "Automations and agents (F29)"}.get(key, key)
        agg[label] = agg.get(label, 0.0) + r["usd"]
    items = sorted(agg.items(), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(8.4, 3.6), facecolor=SURF)
    ys = range(len(items))
    ax.barh(list(ys), [v for _, v in items], color=BLUE, height=0.6)
    for y, (_, v) in zip(ys, items):
        ax.text(v, y, f" ${v:.2f}", va="center", fontsize=8, color=INK2)
    ax.set_yticks(list(ys), [k for k, _ in items])
    style(ax, xlabel="USD at Moonshot list price (input $3, output $15 per million tokens)", grid="x")
    ax.set_title(f"Kimi K3 spend across the project: ${d['total']['usd']:.2f} for {d['total']['calls']:,} calls",
                 loc="left")
    fig.tight_layout()
    return save(fig, out, "kimi_costs.png")


def fig_verified(out: Path) -> Path | None:
    """Held-out set: what each system says, judged; the four outcomes stacked."""
    jd = ROOT / "results/verified/judged_heldout.json"
    if not jd.exists():
        return None
    d = json.loads(jd.read_text())
    f = d["files"]
    rows = []
    for fname, var, label in (("answers_heldout.json", "old", "0.5B reads memory,\nevery answer stated"),
                              ("answers_heldout_sa.json", "facts+compress+reader", "0.5B + verified memory\n(CAMR)"),
                              ("answers_heldout_sa.json", "+kimi+cross", "0.5B + verified memory,\nKimi cross-check")):
        v = f.get(fname, {}).get(var)
        if not v:
            continue
        if var == "old":  # unchecked: every first answer stated
            u = v["unchecked"]
            rows.append((label, u["correct"], u["wrong"], 0.0, 1 - u["correct"] - u["wrong"]))
        else:
            x = v["verified"]
            rows.append((label, x["correct"], x["hallucinated"], x["other_meaning"], x["unconfirmed"]))
    for model, label in (("kimi-k3", "Kimi K3 alone\n(cloud, closed-book)"), ("llama3.2:3b", "Llama 3B alone"),
                         ("qwen2.5:0.5b", "Qwen 0.5B alone")):
        c = d.get("closed", {}).get(model)
        if c:
            rows.append((label, c["correct"], c["wrong"], 0.0, 1 - c["correct"] - c["wrong"]))
    fig, ax = plt.subplots(figsize=(8.6, 4.2), facecolor=SURF)
    ys = list(range(len(rows)))[::-1]
    for y, (label, c, w, o, u) in zip(ys, rows):
        left = 0.0
        for val, col in ((c, GREEN), (w, RED), (o, BLUE), (u, GREY)):
            ax.barh(y, 100 * val, left=left, color=col, edgecolor=SURF, linewidth=1.5, height=0.68)
            if val >= 0.05:
                ax.text(left + 50 * val, y, f"{100 * val:.1f}" if val < 0.1 else f"{100 * val:.0f}", ha="center",
                        va="center", fontsize=7.5, color="white")
            left += 100 * val
    ax.set_yticks(ys, [r[0] for r in rows], fontsize=8)
    ax.set_xlim(0, 100)
    style(ax, xlabel="% of 200 held-out PopQA questions (judged)", grid="x")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREEN, RED, BLUE, GREY)]
    ax.legend(handles, ["correct", "wrong, stated as fact", "about another meaning (named)", "not confirmed / declined"],
              frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.45, -0.16), ncol=4)
    ax.set_title("Held-out questions: how often each system states a wrong fact", loc="left")
    fig.tight_layout()
    return save(fig, out, "verified_outcomes.png")


def fig_rag_errors(out: Path) -> Path | None:
    """Why wrong answers happen: the gold answer was in what the reader got (it misread) or it was not (retrieval
    missed and the reader answered anyway)."""
    runs = rag_runs()
    readers = [(r, n) for r, n in READERS if any((r, p) in runs for p in ORDER)]
    if not readers:
        return None
    fig, axes = plt.subplots(1, len(readers), figsize=(4.2 * len(readers) + 1.2, 4.2), facecolor=SURF, sharey=True)
    axes = [axes] if len(readers) == 1 else list(axes)
    pipes = [p for p in ORDER if any((r, p) in runs for r, _ in readers)]
    ys = list(range(len(pipes)))[::-1]
    for ax, (reader, name) in zip(axes, readers):
        for y, p in zip(ys, pipes):
            if (reader, p) not in runs:
                ax.text(1, y, "not run", va="center", fontsize=7, color=INK2)
                continue
            d = runs[(reader, p)]
            judged = d.get("judged", {})
            rows = d["per_question"]
            ok = lambda r: judged.get(str(r["i"]), r["exact"])  # noqa: E731
            wrong = [r for r in rows if r["stated"] and not ok(r)]
            misread = 100 * sum(r["gold_in_context"] for r in wrong) / len(rows)
            missed = 100 * sum(not r["gold_in_context"] for r in wrong) / len(rows)
            ax.barh(y, misread, color=ORANGE, edgecolor=SURF, linewidth=1.5, height=0.68)
            ax.barh(y, missed, left=misread, color=RED, edgecolor=SURF, linewidth=1.5, height=0.68)
            if misread >= 5:
                ax.text(misread / 2, y, f"{misread:.0f}", ha="center", va="center", fontsize=7.5, color="white")
            if missed >= 5:
                ax.text(misread + missed / 2, y, f"{missed:.0f}", ha="center", va="center", fontsize=7.5,
                        color="white")
        ax.set_yticks(ys, [PIPE_LABEL[p] for p in pipes])
        ax.set_xlim(0, 70)
        style(ax, xlabel="wrong answers stated, % of 200 questions", grid="x")
        ax.set_title(name, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (ORANGE, RED)]
    fig.legend(handles, ["the answer was in what it read (misread)", "the answer was not in what it read (answered "
                         "anyway)"], frameon=False, fontsize=8.5, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Where the wrong answers come from", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    return save(fig, out, "rag_errors.png")


def fig_agent_matrix(out: Path) -> Path | None:
    cfgs = [("llama3_2_3b__none", "3B, none"), ("llama3_2_3b__rag", "3B + RAG"), ("llama3_2_3b__camr", "3B + CAMR"),
            ("kimi-k3__none", "Kimi, none"), ("kimi-k3__rag", "Kimi + RAG"), ("kimi-k3__camr", "Kimi + CAMR")]
    rows = [(n, json.loads((AG / f"agent_{t}.json").read_text())["per_task"]) for t, n in cfgs
            if (AG / f"agent_{t}.json").exists()]
    if not rows:
        return None
    tasks = [t["task"] for t in rows[0][1]]
    fig, ax = plt.subplots(figsize=(10.4, 0.5 * len(rows) + 1.6), facecolor=SURF)
    for y, (name, per) in enumerate(rows):
        by = {t["task"]: t for t in per}
        for x, tid in enumerate(tasks):
            t = by.get(tid, {})
            if t.get("success"):
                col, mark = GREEN, ""
            elif t.get("hallucinated_action"):
                col, mark = RED, "!"
            elif t.get("escalated"):
                col, mark = GREY, "→"
            else:
                col, mark = ORANGE, "×"
            ax.add_patch(plt.Rectangle((x + 0.05, len(rows) - 1 - y + 0.08), 0.9, 0.84, color=col))
            if mark:
                ax.text(x + 0.5, len(rows) - 1 - y + 0.5, mark, ha="center", va="center", fontsize=8, color="white")
    ax.set_xlim(0, len(tasks))
    ax.set_ylim(0, len(rows))
    ax.set_xticks([x + 0.5 for x in range(len(tasks))], tasks, fontsize=7, rotation=90)
    ax.set_yticks([len(rows) - 1 - y + 0.5 for y in range(len(rows))], [n for n, _ in rows], fontsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREEN, GREY, ORANGE, RED)]
    ax.legend(handles, ["succeeded", "handed to a person (→)", "failed (×)", "hallucinated action (!)"],
              frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=4)
    ax.set_title("Every agent task, every configuration (A17–A19 should be handed to a person)", loc="left")
    fig.tight_layout()
    return save(fig, out, "agentic_matrix.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/figures/report")
    o = Path(ap.parse_args().out)
    o.mkdir(parents=True, exist_ok=True)
    for f in (fig_verified, fig_rag_errors, fig_agent_matrix, fig_rag_outcomes, fig_rag_tradeoff, fig_rag_cost, fig_models, fig_desk, fig_agent, fig_fresh, fig_costs):
        f(o)
