"""GapAnalyzer (FR-15): fraction of the capability gap closed, per task type.

    gap = (S_treatment - S_floor) / (S_ceiling - S_floor)        (Equation 3.1)

Every comparison is paired: only questions answered successfully under all
three conditions enter the calculation, and the bootstrap resamples *questions*,
recomputing all three means per resample.

Equation 3.1 is a ratio, and a ratio with a small denominator is unstable: if
the ceiling barely beats the floor on some task type (plausible on GSM8K with a
strong 3B model) a two-point accuracy wobble becomes a gap of +/-0.5.  The
analyser therefore always reports the raw absolute gain alongside the gap, flags
any task type whose denominator is below ``min_denominator``, and reports how
many bootstrap resamples had a usable denominator.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

TASK_TYPES = {"popqa": "single_hop", "hotpotqa": "multi_hop", "2wikimultihopqa": "multi_hop", "gsm8k": "reasoning"}


@dataclass
class GapResult:
    label: str
    group: str
    n: int
    n_failed: int
    floor: float
    ceiling: float
    treatment: float
    absolute_gain: float
    denominator: float
    gap_closed: float | None
    ci_low: float | None
    ci_high: float | None
    valid_resamples: float
    unstable: bool
    mean_context_tokens: float
    mean_prompt_tokens_floor: float | None
    mean_prompt_tokens_treatment: float | None
    median_retrieval_ms: float | None
    median_generation_ms: float | None
    median_e2e_ms: float | None
    retrieval_share: float | None
    gap_per_1k_tokens: float | None
    gain_per_1k_tokens: float | None
    accuracy_per_s: float | None
    budget: int | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _latest_runs(conn: sqlite3.Connection) -> dict[tuple[str, str, str], int]:
    """(label, condition, benchmark) -> most recent completed run_id."""
    rows = conn.execute(
        "SELECT label, condition, benchmark, MAX(run_id) FROM run WHERE status='completed'"
        " GROUP BY label, condition, benchmark"
    ).fetchall()
    return {(r[0], r[1], r[2]): int(r[3]) for r in rows}


def _queries(conn: sqlite3.Connection, run_id: int, metric_by_dataset: dict[str, str]) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT q.query_id, q.question_id, q.dataset, q.task_type, q.status, q.context_tokens, q.prompt_tokens,"
        " q.retrieval_latency_ms, q.generation_latency_ms, q.e2e_latency_ms, q.budget"
        " FROM query_log q WHERE q.run_id=?",
        (run_id,),
    ).fetchall()
    scores: dict[int, dict[str, float]] = defaultdict(dict)
    for qid, metric, value in conn.execute(
        "SELECT s.query_id, s.metric, s.value FROM score s JOIN query_log q USING(query_id) WHERE q.run_id=?",
        (run_id,),
    ):
        scores[qid][metric] = value
    out = {}
    for r in rows:
        (qid, question_id, dataset, task_type, status, ctx, ptok, ret_ms, gen_ms, e2e_ms, budget) = r
        metric = metric_by_dataset.get(dataset, "em")
        out[f"{dataset}/{question_id}"] = {
            "task_type": task_type,
            "status": status,
            "score": scores.get(qid, {}).get(metric),
            "context_tokens": ctx or 0,
            "prompt_tokens": ptok,
            "retrieval_ms": ret_ms,
            "generation_ms": gen_ms,
            "e2e_ms": e2e_ms,
            "budget": budget,
        }
    return out


def _median(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return float(statistics.median(vals)) if vals else None


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return float(sum(vals) / len(vals)) if vals else None


class GapAnalyzer:
    def __init__(
        self,
        conn: sqlite3.Connection,
        primary_metric: dict[str, str],
        *,
        bootstrap: int = 1000,
        ci: float = 0.95,
        min_denominator: float = 0.05,
        seed: int = 13,
        baseline_label: str = "main",
    ):
        self.conn = conn
        self.primary_metric = primary_metric
        self.bootstrap = bootstrap
        self.ci = ci
        self.min_denominator = min_denominator
        self.seed = seed
        self.baseline_label = baseline_label
        self.runs = _latest_runs(conn)

    def treatment_labels(self) -> list[str]:
        labels = sorted({lab for (lab, cond, _b) in self.runs if cond == "treatment"})
        return labels

    def compute(self, label: str, by: str = "task_type") -> list[GapResult]:
        """Gap closed for treatment run(s) ``label`` against the baseline floor/ceiling."""
        grouped: dict[str, list[tuple[float, float, float, dict, dict]]] = defaultdict(list)
        failed: dict[str, int] = defaultdict(int)
        benches = sorted({b for (lab, cond, b) in self.runs if lab == label and cond == "treatment"})
        for bench in benches:
            f_id = self.runs.get((self.baseline_label, "floor", bench))
            c_id = self.runs.get((self.baseline_label, "ceiling", bench))
            t_id = self.runs[(label, "treatment", bench)]
            if f_id is None or c_id is None:
                continue
            F = _queries(self.conn, f_id, self.primary_metric)
            C = _queries(self.conn, c_id, self.primary_metric)
            T = _queries(self.conn, t_id, self.primary_metric)
            for key in sorted(set(F) & set(C) & set(T)):
                f, c, t = F[key], C[key], T[key]
                group = t["task_type"] if by == "task_type" else key.split("/", 1)[0]
                if "failed" in (f["status"], c["status"], t["status"]) or None in (f["score"], c["score"], t["score"]):
                    failed[group] += 1
                    continue
                grouped[group].append((f["score"], c["score"], t["score"], f, t))
        return [self._result(label, g, rows, failed[g]) for g, rows in sorted(grouped.items())]

    def _result(self, label: str, group: str, rows: list, n_failed: int) -> GapResult:
        arr = np.array([(f, c, t) for f, c, t, _, _ in rows], dtype=float)
        n = len(arr)
        mf, mc, mt = arr.mean(axis=0)
        denom = mc - mf
        gap = (mt - mf) / denom if abs(denom) >= 1e-12 else None
        rng = np.random.default_rng(self.seed)
        gaps = []
        for _ in range(self.bootstrap):
            idx = rng.integers(0, n, n)
            bf, bc, bt = arr[idx].mean(axis=0)
            d = bc - bf
            if d >= self.min_denominator:
                gaps.append((bt - bf) / d)
        alpha = (1 - self.ci) / 2
        lo, hi = (float(np.quantile(gaps, alpha)), float(np.quantile(gaps, 1 - alpha))) if gaps else (None, None)

        tq = [t for *_, t in rows]
        fq = [f for *_, f, _ in rows]
        ctx = _mean([t["context_tokens"] for t in tq]) or 0.0
        ret = _median([t["retrieval_ms"] for t in tq])
        e2e = _median([t["e2e_ms"] for t in tq])
        budgets = {t["budget"] for t in tq}
        return GapResult(
            label=label,
            group=group,
            n=n,
            n_failed=n_failed,
            floor=float(mf),
            ceiling=float(mc),
            treatment=float(mt),
            absolute_gain=float(mt - mf),
            denominator=float(denom),
            gap_closed=None if gap is None else float(gap),
            ci_low=lo,
            ci_high=hi,
            valid_resamples=len(gaps) / self.bootstrap if self.bootstrap else 0.0,
            unstable=bool(denom < self.min_denominator),
            mean_context_tokens=float(ctx),
            mean_prompt_tokens_floor=_mean([f["prompt_tokens"] for f in fq]),
            mean_prompt_tokens_treatment=_mean([t["prompt_tokens"] for t in tq]),
            median_retrieval_ms=ret,
            median_generation_ms=_median([t["generation_ms"] for t in tq]),
            median_e2e_ms=e2e,
            retrieval_share=(ret / e2e) if ret is not None and e2e else None,
            gap_per_1k_tokens=(gap / ctx * 1000) if gap is not None and ctx > 0 else None,
            gain_per_1k_tokens=((mt - mf) / ctx * 1000) if ctx > 0 else None,
            accuracy_per_s=(mt / (e2e / 1000)) if e2e else None,
            budget=budgets.pop() if len(budgets) == 1 else None,
        )

    # ---------------------------------------------------------- tables
    def ablation_table(self, labels: list[str], control: str = "control", by: str = "task_type") -> list[dict]:
        """One row per (variant, group): gap closed and deltas against the control (Table 4.7)."""
        results = {lab: {r.group: r for r in self.compute(lab, by)} for lab in labels}
        base = results.get(control, {})
        rows = []
        for lab in labels:
            for group, r in results[lab].items():
                b = base.get(group)
                rows.append({
                    "variant": lab,
                    "group": group,
                    "n": r.n,
                    "gap_closed": r.gap_closed,
                    "ci_low": r.ci_low,
                    "ci_high": r.ci_high,
                    "absolute_gain": r.absolute_gain,
                    "unstable": r.unstable,
                    "context_tokens": r.mean_context_tokens,
                    "median_e2e_ms": r.median_e2e_ms,
                    "delta_gap_closed": _delta(r.gap_closed, b.gap_closed if b else None),
                    "delta_tokens_per_query": _delta(r.mean_context_tokens, b.mean_context_tokens if b else None),
                    "delta_latency_ms": _delta(r.median_e2e_ms, b.median_e2e_ms if b else None),
                })
        return rows

    def budget_sweep(self, labels: list[str], by: str = "task_type") -> tuple[list[dict], dict[str, dict]]:
        """Gap closed and gap closed per 1k tokens against budget; the optimum per group (objective v)."""
        rows = []
        for lab in labels:
            for r in self.compute(lab, by):
                rows.append({
                    "variant": lab,
                    "group": r.group,
                    "budget": r.budget,
                    "gap_closed": r.gap_closed,
                    "ci_low": r.ci_low,
                    "ci_high": r.ci_high,
                    "context_tokens": r.mean_context_tokens,
                    "gap_per_1k_tokens": r.gap_per_1k_tokens,
                    "median_e2e_ms": r.median_e2e_ms,
                    "unstable": r.unstable,
                })
        rows.sort(key=lambda x: (x["group"], x["budget"] if x["budget"] is not None else -1))
        optimum: dict[str, dict] = {}
        for group in sorted({r["group"] for r in rows}):
            g = [r for r in rows if r["group"] == group and r["budget"] and r["gap_per_1k_tokens"] is not None]
            if not g:
                continue
            best = max(g, key=lambda r: r["gap_per_1k_tokens"])
            with_gap = [r for r in g if r["gap_closed"] is not None]
            top = max((r["gap_closed"] for r in with_gap), default=None)
            saturation = None
            if top is not None and top > 0:
                saturation = min(r["budget"] for r in with_gap if r["gap_closed"] >= 0.95 * top)
            optimum[group] = {
                "best_budget_per_token": best["budget"],
                "gap_per_1k_tokens": best["gap_per_1k_tokens"],
                "max_gap_closed": top,
                "saturation_budget": saturation,
            }
        return rows, optimum


def _delta(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else float(a - b)
