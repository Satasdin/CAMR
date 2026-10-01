"""Retrieval-level evaluation: does the read path put the gold evidence in front of
the model?  Needs no language model, so it runs anywhere the embedder runs.

For multi-hop benchmarks with labelled supporting paragraphs (HotpotQA, 2Wiki),
each configuration is scored on every sampled question by:

* support_all      both (all) gold supporting paragraphs are in the admitted context
* support_any      at least one is
* answer_in_ctx    the gold answer string appears in the admitted context
* context_tokens   tokens actually supplied (budget is a ceiling under gating)
* retrieval_ms     embed through packing, per question

This isolates the memory engine from the reader: if the evidence never reaches
the context, no small model can use it, and the ceiling of the treatment
condition is ``support_all``.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass

from camr.config import Config
from camr.eval.scoring import normalize_answer
from camr.harness.benchmarks import Question
from camr.harness.experiment import Workspace
from camr.memory.clock import LogicalClock


@dataclass
class RetrievalRow:
    label: str
    benchmark: str
    n: int
    budget: int
    support_all: float
    support_any: float
    answer_in_context: float
    abstain_rate: float
    mean_context_tokens: float
    support_all_per_1k_tokens: float | None
    median_retrieval_ms: float
    p95_retrieval_ms: float
    bridged_per_query: float

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _contains(text: str, golds: list[str]) -> bool:
    t = f" {normalize_answer(text)} "
    return any(normalize_answer(g) and f" {normalize_answer(g)} " in t for g in golds)


def evaluate(ws: Workspace, label: str, cfg: Config, benchmark: str, questions: list[Question]) -> RetrievalRow:
    store = ws.store
    nt = cfg.memory.note_type
    store.reset_access_state(nt)
    clock = LogicalClock(store.latest_created_at(nt), cfg.memory.clock_step_hours)
    engine = ws.engine(cfg, clock)
    engine.recall("warm-up query")  # first call loads lazily initialised state
    store.reset_access_state(nt)
    s_all = s_any = ans = abst = bridged = 0
    tokens, times = [], []
    qs = [q for q in questions if q.support]
    for q in qs:
        t0 = time.perf_counter()
        r = engine.recall(q.question)
        times.append((time.perf_counter() - t0) * 1000)
        titles = store.note_titles(c.note.note_id for c in r.admitted)
        got = {" ".join((t or "").split()) for t in titles.values()}
        gold = {" ".join(t.split()) for t in q.support}
        s_all += gold <= got
        s_any += bool(gold & got)
        ans += _contains(r.context, q.answers)
        abst += r.abstained
        bridged += sum(1 for c in r.admitted if c.via is not None)
        tokens.append(r.context_tokens)
        clock.tick()
    n = len(qs)
    mean_tok = sum(tokens) / n
    times.sort()
    return RetrievalRow(
        label=label, benchmark=benchmark, n=n, budget=cfg.memory.token_budget,
        support_all=s_all / n, support_any=s_any / n, answer_in_context=ans / n, abstain_rate=abst / n,
        mean_context_tokens=mean_tok,
        support_all_per_1k_tokens=(s_all / n) / mean_tok * 1000 if mean_tok else None,
        median_retrieval_ms=statistics.median(times), p95_retrieval_ms=times[min(n - 1, int(0.95 * n))],
        bridged_per_query=bridged / n,
    )


# Read-path configurations compared (write path fixed to verbatim: no model needed).
_NO_GATE = {"min_similarity": 0.0, "similarity_margin": None}
VARIANTS: list[tuple[str, dict]] = [
    ("control", {"retrieval_policy": "similarity_only", "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0},
                 "expansion": "none", **_NO_GATE}),
    ("composite", {"expansion": "none", **_NO_GATE}),
    ("gated", {"expansion": "none"}),
    ("bridged-ungated", {"expansion": "entity", **_NO_GATE}),
    ("bridged", {"expansion": "entity"}),
    # Similarity ranking + gating + bridging: drops the recency/importance terms.
    ("bridged-sim", {"retrieval_policy": "similarity_only",
                     "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0}, "expansion": "entity"}),
]
SWEEP_LABELS = ("control", "bridged-ungated", "bridged-sim")
SWEEP_BUDGETS = (64, 128, 256, 512, 1024)


def run_all(ws: Workspace, cfg: Config, benchmarks: list[str]) -> list[dict]:
    base = cfg.with_overrides({"memory": {"write_policy": "verbatim", "screening": True}})
    rows = []
    for bench in benchmarks:
        qs = ws.sample(bench)
        for label, over in VARIANTS:
            vcfg = base.with_overrides({"memory": over})
            rows.append(evaluate(ws, label, vcfg, bench, qs).as_dict())
            if label in SWEEP_LABELS:
                for b in SWEEP_BUDGETS:
                    if b == vcfg.memory.token_budget:
                        continue
                    bcfg = vcfg.with_overrides({"memory": {"token_budget": b}})
                    rows.append(evaluate(ws, f"{label}@{b}", bcfg, bench, qs).as_dict())
    return rows
