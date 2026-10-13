"""Figures for the method, tuning and fine-tuning sections of Chapter 5, computed from logged results.

    python scripts/make_method_figures.py --out docs/figures/report
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mrf", HERE / "make_report_figures.py")
mrf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mrf)
plt, style, save = mrf.plt, mrf.style, mrf.save
BLUE, ORANGE, GREEN, GREY, INK, INK2, GRID, SURF = mrf.BLUE, mrf.ORANGE, mrf.GREEN, mrf.GREY, mrf.INK, mrf.INK2, mrf.GRID, mrf.SURF
ROOT = HERE.parent


# ------------------------------------------------------------------ the read path on one real question
def fig_gating_trace(out: Path) -> Path:
    """Candidates for 'Who was the director of The Loudwater Mystery?' (pilot, 0.5B + CAMR): which notes the
    gate admitted and why (tau = 0.50, delta = 0.15)."""
    c = sqlite3.connect(f"file:{ROOT / 'results/pilot/camr.sqlite'}?mode=ro", uri=True)
    qid = c.execute("SELECT query_id FROM query_log WHERE run_id=21 AND question_id='5939255'").fetchone()[0]
    rows = c.execute("SELECT r.similarity, r.admitted, r.tokens, s.title FROM retrieved_note r JOIN note n USING(note_id) "
                     "JOIN source s USING(source_id) WHERE r.query_id=? ORDER BY r.similarity DESC LIMIT 10", (qid,)).fetchall()
    sims = [r[0] for r in rows]
    best, tau, delta = sims[0], 0.50, 0.15
    fig, ax = plt.subplots(figsize=(7.6, 3.9), facecolor=SURF)
    ys = range(len(rows))
    cols = [BLUE if r[1] else GREY for r in rows]
    ax.barh(list(ys), sims, color=cols, height=0.68, edgecolor=SURF)
    for y, (s, adm, tok, title) in zip(ys, rows):
        ax.text(0.302, y, f"{(title or '')[:34]}", va="center", fontsize=7.6, color=SURF if adm else INK)
        ax.text(s + 0.004, y, f"{s:.3f}" + (f"  admitted · {tok} tokens" if adm else ""), va="center", fontsize=7.6,
                color=INK2)
    ax.axvline(tau, color=ORANGE, lw=1.4, ls="--")
    ax.axvline(best - delta, color=GREEN, lw=1.4, ls="--")
    ax.text(tau, len(rows) - 0.35, f" τ = {tau:.2f}\n abstain below", color=ORANGE, fontsize=7.6, va="top")
    ax.text(best - delta, len(rows) - 0.35, f" s(1) − δ = {best:.3f} − {delta:.2f} = {best - delta:.3f}\n admit at or above",
            color=GREEN, fontsize=7.6, va="top")
    ax.set_xlim(0.3, 0.86)
    ax.set_ylim(len(rows) - 0.4 + 1.2, -0.6)
    ax.set_yticks([])
    style(ax, xlabel="cosine similarity to the question (BGE-small)")
    ax.set_title("Gating on a real question: 1 of 20 candidates admitted (47 of a 512-token budget)", loc="left")
    return save(fig, out, "gating_trace.png")


def fig_bridge_trace(out: Path) -> Path:
    """The two multi-hop examples of the n = 200 study: admitted notes, their similarity, and which came by bridging."""
    ex = json.loads((ROOT / "docs/results/examples.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.7), facecolor=SURF)
    for ax, key in zip(axes, ("bridge_1", "bridge_2")):
        e = ex[key]
        adm = [n for n in e["trace"] if n["admitted"]][:7]
        ys = range(len(adm))
        ax.barh(list(ys), [n["similarity"] for n in adm], color=[ORANGE if n["via_bridge"] else BLUE for n in adm],
                height=0.66, edgecolor=SURF)
        for y, n in zip(ys, adm):
            t = n["title"] or ""
            ax.text(0.01, y, t if len(t) <= 44 else t[:42] + "…", va="center", fontsize=6.9, color=SURF)
            ax.text(n["similarity"] + 0.01, y, f"{n['similarity']:.2f}" + ("  via bridge" if n["via_bridge"] else ""),
                    va="center", fontsize=7.2, color=INK2)
        ax.set_xlim(0, 1.0)
        ax.invert_yaxis()
        ax.set_yticks([])
        style(ax, xlabel="similarity to the question")
        q = e["question"]
        ax.set_title((q[:58] + "…") if len(q) > 60 else q, loc="left", fontsize=8.6)
    fig.suptitle("Admitted notes for two multi-hop questions (llama3.2:3b + CAMR, both answered correctly); "
                 "orange = reached only by entity bridging", x=0.01, ha="left", fontsize=9.2, fontweight="bold")
    fig.tight_layout()
    return save(fig, out, "bridge_trace.png")


# ------------------------------------------------------------------ tuning the learned router
def fig_router_tuning(out: Path) -> Path | None:
    p = ROOT / "results/learn/tables/policy_tuning.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.5), facecolor=SURF)
    ax = axes[0]
    for (name, col) in zip(("task only", "task + retrieval", "full (with interactions)"), (BLUE, ORANGE, GREEN)):
        g = [r for r in d["router_grid"] if r["features"] == name]
        x = [r["lambda"] for r in g]
        ax.errorbar(x, [r["cv_reward"] for r in g], yerr=[r["cv_reward_sd"] / np.sqrt(5) for r in g], color=col,
                    marker="o", ms=4, lw=1.6, capsize=2, label=name)
    ax.set_xscale("log")
    style(ax, xlabel="ridge penalty λ (log)", ylabel="5-fold CV mean reward", grid="y")
    ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    ax.set_title("Router: λ × feature set", loc="left")
    ax = axes[1]
    for alpha, col in zip((0.0, 0.25, 0.5, 1.0, 2.0), (GREY, ORANGE, BLUE, GREEN, INK2)):
        g = [r for r in d["linucb_grid"] if r["alpha"] == alpha]
        ax.plot([r["passes"] for r in g], [r["cv_reward"] for r in g], marker="o", ms=3.5, lw=1.5, color=col,
                label=f"α = {alpha:g}")
    style(ax, xlabel="passes over the 144 training questions (epochs)", grid="y")
    ax.legend(frameon=False, fontsize=7.5, ncol=2)
    ax.set_title("LinUCB: exploration α × epochs", loc="left")
    ax = axes[2]
    g = d["cascade_grid"]
    ax.plot([r["threshold"] for r in g], [r["cv_reward"] for r in g], color=BLUE, marker="o", ms=3.5, lw=1.6, label="CV reward")
    ax.plot([r["threshold"] for r in g], [r["cv_accuracy"] for r in g], color=GREEN, marker="o", ms=3.5, lw=1.6,
            label="CV accuracy")
    ax.axvline(d["cascade_selected"], color=ORANGE, ls="--", lw=1.2)
    ax.text(d["cascade_selected"] + 0.02, ax.get_ylim()[0] + 0.02, f"selected {d['cascade_selected']:.2f}", color=ORANGE,
            fontsize=7.6)
    style(ax, xlabel="escalation threshold θ", grid="y")
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("Cascade: escalation threshold", loc="left")
    fig.suptitle("Hyperparameters chosen by 5-fold cross-validation on the training split only (error bars: ±1 s.e. over folds)",
                 x=0.01, ha="left", fontsize=9.2, fontweight="bold")
    fig.tight_layout()
    return save(fig, out, "router_tuning.png")


def fig_heldout_policies(out: Path) -> Path | None:
    p = ROOT / "results/learn/tables/policy_tuning.json"
    if not p.exists():
        return None
    h = json.loads(p.read_text())["held_out"]
    names = ["always cloud", "tuned LinUCB", "tuned router", "tuned router + cascade"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 2.9), facecolor=SURF, gridspec_kw={"width_ratios": [1.5, 1]})
    ax = axes[0]
    acc = [h[n]["accuracy"] * 100 for n in names]
    lo = [h[n]["vs_always_cloud"][1] * 100 if "vs_always_cloud" in h[n] else 0 for n in names]
    hi = [h[n]["vs_always_cloud"][2] * 100 if "vs_always_cloud" in h[n] else 0 for n in names]
    base = h["always cloud"]["accuracy"] * 100
    ax.barh(names, acc, color=[GREY, ORANGE, BLUE, GREEN], height=0.62, edgecolor=SURF)
    for i, n in enumerate(names):
        txt = f"{acc[i]:.1f}%"
        if "vs_always_cloud" in h[n]:
            txt += f"   Δ vs cloud {h[n]['vs_always_cloud'][0] * 100:+.1f} (95% CI {lo[i]:+.1f} to {hi[i]:+.1f})"
        ax.text(acc[i] + 0.8, i, txt, va="center", fontsize=7.6, color=INK2)
    ax.axvline(base, color=INK2, lw=0.8, ls=":")
    ax.set_xlim(0, 120)
    style(ax, xlabel="held-out accuracy, n = 72 (%)")
    ax.set_title("Accuracy", loc="left")
    ax = axes[1]
    lat = [h[n]["mean_latency_s"] for n in names]
    share = [h[n]["cloud_share"] * 100 for n in names]
    ax.barh(names, lat, color=[GREY, ORANGE, BLUE, GREEN], height=0.62, edgecolor=SURF)
    for i in range(len(names)):
        ax.text(lat[i] + 0.2, i, f"{lat[i]:.1f} s · {share[i]:.0f}% to cloud", va="center", fontsize=7.6, color=INK2)
    ax.set_yticks([])
    ax.set_xlim(0, 19)
    style(ax, xlabel="mean seconds per answer")
    ax.set_title("Time and cloud use", loc="left")
    fig.tight_layout()
    return save(fig, out, "heldout_policies.png")


# ------------------------------------------------------------------ tuning the read path
def fig_gating_tuning(out: Path) -> Path | None:
    p = ROOT / "results/retrieval_eval/tables/gating_tuning.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    margins = [m for m in d["margins"]]
    budgets = d["budgets"]
    lab = ["none" if m is None else f"{m:.2f}" for m in margins]
    grid = {(g["margin"], g["budget"]): g for g in d["validation_grid"]}
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.3), facecolor=SURF)
    for ax, key, title, fmt, cmap in ((axes[0], "support_all", "Full-support recall (%)", "{:.1f}", "Blues"),
                                      (axes[1], "mean_tokens", "Tokens supplied", "{:.0f}", "Oranges"),
                                      (axes[2], "J", "Objective J = recall − 0.1 × tokens/1000", "{:.3f}", "Greens")):
        M = np.array([[grid[(m, b)][key] * (100 if key == "support_all" else 1) for b in budgets] for m in margins])
        im = ax.imshow(M, cmap=cmap, aspect="auto")
        for i in range(len(margins)):
            for j in range(len(budgets)):
                v = M[i, j]
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=7.4,
                        color=SURF if v > (M.min() + M.max()) / 2 else INK)
        ax.set_xticks(range(len(budgets)), budgets)
        ax.set_yticks(range(len(margins)), lab)
        ax.set_xlabel("token budget B", color=INK2)
        ax.set_ylabel("margin δ", color=INK2)
        ax.set_title(title, loc="left", fontsize=9)
        ax.tick_params(labelsize=8)
        sel = d["selected"]
        i, j = margins.index(sel["margin"]), budgets.index(sel["budget"])
        ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec=INK, lw=1.8))
    fig.suptitle(f"Read-path tuning on the validation half ({d['n_val']} multi-hop questions); "
                 "the box marks the selected setting", x=0.01, ha="left", fontsize=9.2, fontweight="bold")
    fig.tight_layout()
    return save(fig, out, "gating_tuning.png")


def fig_tau_tradeoff(out: Path) -> Path | None:
    """The abstain threshold: share of relevant notes kept vs off-topic notes rejected, as tau varies."""
    files = [("BGE-small (benchmarks)", ROOT / "docs/calibration/gating_bge_values.json", BLUE),
             ("nomic-embed-text (app)", ROOT / "docs/calibration/gating_nomic_values.json", GREEN)]
    files = [f for f in files if f[1].exists()]
    if not files:
        return None
    fig, ax = plt.subplots(figsize=(6.8, 3.5), facecolor=SURF)
    taus = np.linspace(0.3, 0.8, 101)
    for name, path, col in files:
        d = json.loads(path.read_text())
        rel, irr = np.array(d["relevant_values"]), np.array(d["irrelevant_values"])
        kept = [(rel >= t).mean() * 100 for t in taus]
        rej = [(irr < t).mean() * 100 for t in taus]
        ax.plot(taus, kept, color=col, lw=1.8, label=f"{name}: relevant kept")
        ax.plot(taus, rej, color=col, lw=1.8, ls="--", label=f"{name}: off-topic rejected")
        thr = d["min_similarity_same_rule_as_benchmarks"]
        ax.axvline(thr, color=col, lw=0.8, ls=":")
        ax.text(thr + 0.004, 4, f"τ = {thr:.2f}", color=col, fontsize=7.6, rotation=90, va="bottom")
    style(ax, xlabel="abstain threshold τ", ylabel="% of 200 HotpotQA questions", grid="y")
    ax.legend(frameon=False, fontsize=7.2, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    ax.set_title("Choosing τ: keep relevant notes, reject off-topic ones", loc="left")
    return save(fig, out, "tau_tradeoff.png")


# ------------------------------------------------------------------ fine-tuning baseline
def fig_finetune_curves(out: Path) -> Path | None:
    p = ROOT / "results/finetune/tune/grid.json"
    if not p.exists():
        return None
    runs = json.loads(p.read_text())
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.4), facecolor=SURF)
    cols = {("chat", 1e-4): BLUE, ("chat", 3e-4): GREEN, ("raw", 1e-4): ORANGE, ("raw", 3e-4): INK2}
    for r in runs:
        col = cols.get((r["fmt"], r["lr"]), GREY)
        lab = f"{r['fmt']} format, lr {r['lr']:g}"
        ep = [e["epoch"] for e in r["epochs"]]
        axes[0].plot(ep, [e["train_loss"] for e in r["epochs"]], color=col, marker="o", ms=3, lw=1.6, label=lab)
        ev = [e for e in r["epochs"] if "val_closed" in e]
        axes[1].plot([e["epoch"] for e in ev], [e["val_closed"] * 100 for e in ev], color=col, marker="o", ms=4, lw=1.6,
                     label=lab)
    style(axes[0], xlabel="epoch", ylabel="training loss (cross-entropy)", grid="y")
    axes[0].set_title("LoRA training loss", loc="left")
    axes[0].legend(frameon=False, fontsize=7.4)
    axes[1].set_ylim(0, 25)  # from zero: the changes are one or two questions out of 60
    style(axes[1], xlabel="epoch (evaluated after 1, 2, 4 and 8)", ylabel="validation accuracy, closed book (%)", grid="y")
    axes[1].set_title("Validation accuracy (60 PopQA questions)", loc="left")
    fig.suptitle("Fine-tuning Qwen2.5-0.5B-Instruct with LoRA on the stored documents (selection on validation only)",
                 x=0.01, ha="left", fontsize=9.2, fontweight="bold")
    fig.tight_layout()
    return save(fig, out, "finetune_curves.png")


def fig_finetune_vs_camr(out: Path) -> Path | None:
    p = ROOT / "results/finetune/test.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    b, lo = d["conditions"]["base"], d["conditions"]["lora"]
    names = ["Base model alone", "Base + CAMR", "LoRA fine-tuned", "LoRA fine-tuned + CAMR"]
    acc = [b["test_closed"]["accuracy"], b["test_camr"]["accuracy"], lo["test_closed"]["accuracy"],
           lo["test_camr"]["accuracy"]]
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.0), facecolor=SURF, gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    ax.barh(names, [a * 100 for a in acc], color=[GREY, BLUE, ORANGE, GREEN], height=0.62, edgecolor=SURF)
    for i, a in enumerate(acc):
        ax.text(a * 100 + 1, i, f"{a * 100:.1f}%", va="center", fontsize=8, color=INK2)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    style(ax, xlabel=f"held-out PopQA accuracy, n = {d['n_test']} (%)")
    ax.set_title("Long-tail facts: memory vs fine-tuning", loc="left")
    ax = axes[1]
    g = [b["gsm8k"]["accuracy"] * 100, lo["gsm8k"]["accuracy"] * 100]
    ax.bar(["base", "LoRA"], g, color=[GREY, ORANGE], width=0.55, edgecolor=SURF)
    for i, v in enumerate(g):
        ax.text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=8, color=INK2)
    ax.set_ylim(0, max(g) * 1.35 + 5)
    style(ax, ylabel=f"GSM8K accuracy, n = {d['n_gsm8k']} (%)", grid="y")
    ax.set_title("Side effect on maths", loc="left")
    fig.tight_layout()
    return save(fig, out, "finetune_vs_camr.png")


# ------------------------------------------------------------------ interface design
def fig_design_tokens(out: Path) -> Path | None:
    p = ROOT / "docs/results/ui_audit.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    after, before = d.get("after", {}).get("contrast", []), {(r["theme"], r["fg"], r["bg"]): r for r in d.get("before", {}).get("contrast", [])}
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6), facecolor=SURF)
    for ax, theme in zip(axes, ("dark", "light")):
        rows = [r for r in after if r["theme"] == theme]
        for i, r in enumerate(rows):
            y = len(rows) - 1 - i
            ax.add_patch(plt.Rectangle((0, y + 0.08), 4.3, 0.84, color=r["bg_hex"], ec=GRID, lw=0.6))
            ax.text(0.15, y + 0.5, "Aa  " + r["use"].split(",")[0][:26], color=r["fg_hex"], va="center", fontsize=8.0,
                    fontweight="bold" if r["size"] == "large" else "normal")
            b = before.get((theme, r["fg"], r["bg"]))
            was = f"was {b['ratio']:.2f} → " if b and abs(b["ratio"] - r["ratio"]) > 0.005 else ""
            ax.text(4.45, y + 0.5, f"--{r['fg']} on --{r['bg']}: {was}{r['ratio']:.2f}:1  (AA ≥ {r['required_AA']:g})  "
                    + ("✓" if r["pass_AA"] else "✗"), va="center", fontsize=7.2, color=INK if r["pass_AA"] else ORANGE)
        ax.set_xlim(0, 11)
        ax.set_ylim(0, len(rows))
        ax.axis("off")
        ax.set_title(f"{theme.capitalize()} theme", loc="left", fontsize=9.5)
    fig.suptitle("Design tokens of CAMR Personal with measured WCAG 2.2 contrast (after the audit fixes)", x=0.01,
                 ha="left", fontsize=9.6, fontweight="bold")
    fig.tight_layout()
    return save(fig, out, "design_tokens.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/figures/report")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (fig_gating_trace, fig_bridge_trace, fig_router_tuning, fig_heldout_policies, fig_gating_tuning,
              fig_tau_tradeoff, fig_finetune_curves, fig_finetune_vs_camr, fig_design_tokens):
        f(out)
