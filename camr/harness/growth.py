"""Memory growth over time: same frozen model, more knowledge.

The knowledge corpus (benchmark paragraphs, PopQA pages, GSM8K exemplars) is
shuffled once with the study seed and fed into ONE store in stages, e.g. 25%,
50%, 100%.  After each stage the same small model answers the same fixed
questions.  Because ingestion is incremental, each stage's store contains
everything before it: this is the engine "learning over time" with no change to
the model's weights.

Per stage the experiment records accuracy per task type, how often the answer
is in the store at all, the context actually supplied, retrieval latency, and the
model's OWN prefill and decode timings (from the runtime).  Decode speed is the
direct check that memory leaves the model untouched: it should not move with
store size.
"""

from __future__ import annotations

import random
import statistics
from typing import Any

from camr.config import Config
from camr.eval.analysis import TASK_TYPES
from camr.harness.benchmarks import build_corpus, build_exemplars, check_holdout
from camr.harness.experiment import ExperimentRunner, Workspace


def _shuffled(docs: list, seed: int, name: str) -> list:
    out = list(docs)
    random.Random(f"camr:{seed}:{name}:growth").shuffle(out)
    return out


def _stage_label(frac: float) -> str:
    return f"grow-{round(frac * 100):03d}"


def run_growth(ws: Workspace, cfg: Config, stages: list[float]) -> list[dict[str, Any]]:
    names = list(cfg.benchmarks)
    questions = [q for n in names for q in ws.sample(n)]
    corpora = {}
    for n in names:
        docs = build_corpus(n, cfg.benchmarks[n], ws.sample(n), cfg.seed)
        ex = build_exemplars(cfg.benchmarks[n])
        check_holdout(docs + ex, questions)
        corpora[n] = (_shuffled(docs, cfg.seed, n), _shuffled(ex, cfg.seed, n + "-ex"))
    runner = ExperimentRunner(ws)
    for n in names:  # the reference points every stage is compared with
        runner.run("floor", n, cfg=cfg, label="main")
        runner.run("ceiling", n, cfg=cfg, label="main")
    engine = ws.engine(cfg)
    ex_engine = ws.exemplar_engine(cfg)
    rows = []
    for frac in sorted(stages):
        for n in names:
            docs, ex = corpora[n]
            if docs:
                engine.ingest(docs[: round(frac * len(docs))])
            if ex:
                ex_engine.ingest(ex[: round(frac * len(ex))])
        label = _stage_label(frac)
        for n in names:
            try:
                rid = runner.run("treatment", n, cfg=cfg, label=label)
            except RuntimeError:  # population still empty at this stage
                continue
            rows.append(_summarise(ws, cfg, rid, label, frac, n))
    return rows


def _summarise(ws: Workspace, cfg: Config, run_id: int, label: str, frac: float, bench: str) -> dict[str, Any]:
    metric = cfg.primary_metric.get(bench, "em")
    q = ws.conn.execute(
        "SELECT AVG(s.value) FROM score s JOIN query_log q USING(query_id) WHERE q.run_id=? AND s.metric=?",
        (run_id, metric)).fetchone()[0]
    rows = ws.conn.execute(
        "SELECT context_tokens, retrieval_latency_ms, prefill_ms, decode_ms, generated_tokens, prompt_tokens"
        " FROM query_log WHERE run_id=? AND status='ok'", (run_id,)).fetchall()
    # Model-side speeds from the runtime's own timers: tokens per second of decoding and of prefill.
    dec = [gen / (dec_ms / 1000) for _, _, _, dec_ms, gen, _ in rows if dec_ms and gen]
    pre = [ptok / (pre_ms / 1000) for _, _, pre_ms, _, _, ptok in rows if pre_ms and ptok]
    nt = "exemplar" if TASK_TYPES[bench] == "reasoning" and cfg.memory.reasoning_memory == "exemplars" else cfg.memory.note_type
    med = lambda xs: statistics.median(xs) if xs else None  # noqa: E731
    return {
        "stage": label, "corpus_share": frac, "benchmark": bench, "task_type": TASK_TYPES[bench],
        "notes_in_population": ws.store.count(nt), "store_mb": round(ws.db_path.stat().st_size / 2**20, 1),
        "accuracy": q, "metric": metric, "n": len(rows),
        "mean_context_tokens": statistics.mean([r[0] for r in rows]) if rows else None,
        "median_retrieval_ms": med([r[1] for r in rows if r[1] is not None]),
        "median_prefill_tok_per_s": med(pre),
        "median_decode_tok_per_s": med(dec),
    }
