"""CAMR Inspector: read-only Streamlit interface (FR-17, section 4.4.9).

    streamlit run camr/inspect/app.py -- --run-dir results/2026-09-14
    # or: camr inspect --run-dir results/2026-09-14

Four screens share one frame: Run Dashboard, Ablations, Query Trace, Memory
Store.  The database is opened with mode=ro; no control writes, runs a model,
or starts an experiment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import streamlit as st

from camr import ui_theme
from camr.config import Config
from camr.eval.analysis import GapAnalyzer
from camr.inspect import queries as Q


def _args() -> Path:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    return Path(p.parse_args(sys.argv[1:]).run_dir)


RUN_DIR = _args()
st.set_page_config(page_title="CAMR Inspector", page_icon="◉", layout="wide")
ui_theme.apply(st)


@st.cache_resource
def _conn():
    return Q.connect_ro(RUN_DIR / "camr.sqlite")


@st.cache_resource
def _cfg() -> Config:
    return Config.load(RUN_DIR / "config.yaml")


conn, cfg = _conn(), _cfg()
with st.sidebar:
    ui_theme.brand(st, "Inspector · read-only")
    st.caption(f"{RUN_DIR / 'camr.sqlite'}")
page = st.sidebar.radio("Screen", ["Run Dashboard", "Ablations", "Query Trace", "Memory Store"])
runs = Q.runs(conn)
labels = sorted({r["label"] for r in runs if r["condition"] == "treatment" and not r["label"].startswith("profile")})
_want = st.query_params.get("label", "main")  # ?label=grow-100 opens that treatment directly
label = st.sidebar.selectbox("Treatment label", labels,
                             index=labels.index(_want) if _want in labels else (labels.index("main") if "main" in labels else 0)) if labels else None
analyzer = GapAnalyzer(conn, cfg.primary_metric, bootstrap=cfg.analysis.bootstrap, ci=cfg.analysis.ci,
                       min_denominator=cfg.analysis.min_denominator, seed=cfg.seed)


def gap_track(r: dict) -> None:
    """Floor=0 ... Ceiling=1 track with the treatment marker and its CI (Figure 4.10)."""
    g, lo, hi = r["gap_closed"], r["ci_low"], r["ci_high"]
    cols = st.columns([2, 5, 1.4])
    cols[0].markdown(f"**{r['group']}**  \nn={r['n']}" + (" · :orange[unstable]" if r["unstable"] else ""))
    if g is None:
        cols[1].info("Ceiling does not beat floor: gap undefined")
    else:
        pos = min(max(g, -0.2), 1.2)
        ci = f"CI [{lo:.2f}, {hi:.2f}]" if lo is not None else "CI n/a"
        cols[1].progress(min(max(pos, 0.0), 1.0), text=f"floor {r['floor']:.2f} → treatment {r['treatment']:.2f} → ceiling {r['ceiling']:.2f} · {ci}")
    cols[2].metric("Gap closed", "—" if g is None else f"{g:.2f}")


if page == "Run Dashboard":
    st.header("Run Dashboard")
    if not label:
        st.warning("No completed treatment runs yet.")
        st.stop()
    results = [r.as_dict() for r in analyzer.compute(label)]
    summary = Q.run_summary(conn, label)
    treat = [s for s in summary if s["condition"] == "treatment"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions", sum(s["questions"] for s in treat))
    c2.metric("Mean context tokens / query", f"{sum(s['mean_context_tokens'] or 0 for s in treat) / max(1, len(treat)):.0f}")
    c3.metric("Mean e2e latency", f"{sum(s['mean_e2e_ms'] or 0 for s in treat) / max(1, len(treat)):.0f} ms")
    st.subheader("Fraction of capability gap closed, by task type")
    st.caption(f"Bootstrap {int(cfg.analysis.ci * 100)}% CI · floor = 0, ceiling = 1 · primary metric per dataset: "
               + json.dumps(cfg.primary_metric))
    for r in results:
        gap_track(r)
    st.subheader("Accuracy by condition and task type")
    st.caption("ceiling_rag = the large model given the same notes; residual gap = ceiling_rag − treatment "
               "(what model scale still buys when both models have the same knowledge)")
    st.dataframe([{
        "task type": r["group"], "n": r["n"], "floor": r["floor"], "treatment": r["treatment"], "ceiling": r["ceiling"],
        "ceiling_rag": r["ceiling_rag"],
        "gap closed": r["gap_closed"],
        "95% CI": None if r["ci_low"] is None else f"[{r['ci_low']:.2f}, {r['ci_high']:.2f}]",
        "residual gap": r["residual_gap"],
        "abstain rate": r["abstain_rate"], "context tokens": round(r["mean_context_tokens"]),
    } for r in results], use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    left.subheader("Prompt tokens per query by condition")
    by_cond: dict = {}
    for s_ in summary:
        by_cond.setdefault(s_["condition"], []).append(s_["mean_prompt_tokens"] or 0)
    left.bar_chart({c: sum(v) / len(v) for c, v in by_cond.items()}, horizontal=True)
    right.subheader("Treatment latency: retrieval vs generation (ms)")
    right.bar_chart({"retrieval": sum(s_["mean_retrieval_ms"] or 0 for s_ in treat) / max(1, len(treat)),
                     "generation": sum(s_["mean_generation_ms"] or 0 for s_ in treat) / max(1, len(treat))},
                    horizontal=True)

elif page == "Ablations":
    st.header("Ablation and Budget Sweep")
    variants = [v.label for v in cfg.ablation.variants if v.label in labels]
    if variants:
        st.subheader(f"Ablation table (deltas against '{variants[0]}')")
        st.dataframe(analyzer.ablation_table(variants, control=variants[0]), use_container_width=True)
    sweep = sorted(l for l in labels if l.startswith("budget-"))
    if sweep:
        rows, optimum = analyzer.budget_sweep(sweep)
        st.subheader("Budget sweep")
        for group in sorted({r["group"] for r in rows}):
            g = [r for r in rows if r["group"] == group]
            st.markdown(f"**{group}** · best budget per token: `{optimum.get(group, {}).get('best_budget_per_token')}`"
                        f" · saturation: `{optimum.get(group, {}).get('saturation_budget')}`")
            st.line_chart({"gap closed": {r["budget"]: r["gap_closed"] for r in g},
                           "gap closed / 1k tokens": {r["budget"]: r["gap_per_1k_tokens"] for r in g}})
    if not variants and not sweep:
        st.info("No ablation runs in this directory.")

elif page == "Query Trace":
    st.header("Query Trace")
    treat_runs = [r for r in runs if r["label"] == label and r["condition"] == "treatment"]
    if not treat_runs:
        st.stop()
    run = st.selectbox("Benchmark", treat_runs, format_func=lambda r: f"{r['benchmark']} (run {r['run_id']})")
    qs = Q.questions(conn, run["run_id"])
    q = st.selectbox("Question", qs, format_func=lambda x: f"{x['question_id']}: {x['question'][:90]}")
    t = Q.query_trace(conn, q["dataset"], q["question_id"], label)
    st.markdown(f"**Question:** {q['question']}")
    for a in t["answers"]:
        sc = ", ".join(f"{k} {v:.2f}" for k, v in a["scores"].items())
        st.markdown(f"- **{a['condition']}** ({a['model_name']}): `{(a['answer_text'] or a['error'] or '').strip()[:200]}` "
                    f"· {sc}")
    st.subheader("Retrieval record")
    admitted = [r for r in t["trace"] if r["admitted"]]
    excluded = [r for r in t["trace"] if not r["admitted"]]
    st.dataframe(admitted, use_container_width=True)
    st.markdown("---- *budget cutoff* ----")
    st.dataframe(excluded, use_container_width=True)
    treat = next((a for a in t["answers"] if a["condition"] == "treatment"), None)
    if treat:
        st.subheader(f"Assembled prompt ({treat['context_tokens']} context tokens, budget {treat['budget']})")
        st.code(treat["prompt"] or "", language="text")

else:
    st.header("Memory Store Browser")
    types = Q.note_types(conn)
    if not types:
        st.stop()
    nt = st.selectbox("Note population", types)
    ov = Q.store_overview(conn, nt)
    cols = st.columns(5)
    cols[0].metric("Notes", ov["notes"])
    cols[1].metric("Mean note length", f"{ov['mean_note_tokens']:.1f} tok")
    cols[2].metric("On-disk size", f"{(RUN_DIR / 'camr.sqlite').stat().st_size / 1e6:.1f} MB")
    cols[3].metric("Ingestion yield", "—" if ov["ingestion_yield"] is None else f"{ov['ingestion_yield']:.0%}")
    cols[4].metric("Never retrieved", "—" if ov["never_retrieved_share"] is None else f"{ov['never_retrieved_share']:.0%}")
    ds = st.selectbox("Source dataset", ["(all)"] + sorted({r["dataset"] for r in Q.notes(conn, nt, limit=100000)}))
    never = st.checkbox("Only never-retrieved notes")
    st.dataframe(Q.notes(conn, nt, None if ds == "(all)" else ds, never), use_container_width=True)
    with st.expander("Rejected candidates"):
        st.dataframe(Q.rejections(conn, nt), use_container_width=True)
