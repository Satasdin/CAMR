"""Model-size sweep: the same engine, store and questions across several small models.

For each local model the floor (model alone) and treatment (model + CAMR) are run
on the persisted samples, labelled ``m:<model>``.  All models are compared with
the SAME ceiling run (label ``main``), so gap closed is comparable across sizes.

The report shows, per model and task type, accuracy without and with memory,
the gap closed, and the model's own decode speed with and without memory: the
check that the engine changes what the model reads, not how fast it runs.
"""

from __future__ import annotations

import statistics
from typing import Any

from camr.config import Config
from camr.eval.analysis import TASK_TYPES
from camr.harness.experiment import ExperimentRunner, Workspace


def label_for(model: str) -> str:
    return f"m:{model}"


def run_sweep(ws: Workspace, cfg: Config, models: list[str]) -> None:
    for model in models:
        mcfg = cfg.with_overrides({"local_model": {"name": model}})
        mws = Workspace(mcfg, ws.run_dir, embedder=ws.embedder)  # same store, a runner for this model
        runner = ExperimentRunner(mws)
        for bench in cfg.benchmarks:
            for cond in ("floor", "treatment"):
                runner.run(cond, bench, cfg=mcfg, label=label_for(model))
        mws.close()


def _acc(conn, run_id: int, metric: str) -> float | None:
    return conn.execute("SELECT AVG(s.value) FROM score s JOIN query_log q USING(query_id)"
                        " WHERE q.run_id=? AND s.metric=?", (run_id, metric)).fetchone()[0]


def _decode(conn, run_id: int) -> float | None:
    v = [g / (d / 1000) for g, d in conn.execute(
        "SELECT generated_tokens, decode_ms FROM query_log WHERE run_id=? AND status='ok'", (run_id,)) if g and d]
    return statistics.median(v) if v else None


def _prompt_tokens(conn, run_id: int) -> float | None:
    return conn.execute("SELECT AVG(prompt_tokens) FROM query_log WHERE run_id=? AND status='ok'",
                        (run_id,)).fetchone()[0]


def sweep_report(conn, primary_metric: dict[str, str]) -> list[dict[str, Any]]:
    latest = {(lab, cond, b): rid for lab, cond, b, rid in conn.execute(
        "SELECT label, condition, benchmark, MAX(run_id) FROM run WHERE status='completed'"
        " GROUP BY label, condition, benchmark")}
    models = sorted({lab for lab, _, _ in latest if lab.startswith("m:")})
    out = []
    for lab in models:
        for bench in sorted({b for l2, _, b in latest if l2 == lab}):
            f, t, c = latest.get((lab, "floor", bench)), latest.get((lab, "treatment", bench)), latest.get(("main", "ceiling", bench))
            if not (f and t):
                continue
            metric = primary_metric.get(bench, "em")
            sf, st = _acc(conn, f, metric), _acc(conn, t, metric)
            sc = _acc(conn, c, metric) if c else None
            k = latest.get(("kimi", "ceiling", bench))
            sk = _acc(conn, k, metric) if k else None
            denom = None if sc is None else sc - sf
            df, dt = _decode(conn, f), _decode(conn, t)
            out.append({
                "model": lab[2:], "benchmark": bench, "task_type": TASK_TYPES[bench], "metric": metric,
                "floor": sf, "with_memory": st, "ceiling_20b": sc, "gain": st - sf,
                "gap_closed": (st - sf) / denom if denom and abs(denom) >= 0.05 else None,
                "beats_ceiling": None if sc is None else st > sc,
                "ceiling_kimi": sk,
                "gap_closed_vs_kimi": (st - sf) / (sk - sf) if sk is not None and sk - sf >= 0.05 else None,
                "decode_tok_s_floor": df, "decode_tok_s_memory": dt,
                "decode_change_pct": (dt / df - 1) * 100 if df and dt else None,
                "prompt_tokens_floor": _prompt_tokens(conn, f), "prompt_tokens_memory": _prompt_tokens(conn, t),
            })
    return out


def merge_runs(dst, src) -> int:
    """Copy completed runs (with their queries and scores) from another results database.

    Used to combine model sweeps executed on different machines.  Retrieval traces
    are not copied: note ids differ between stores.  Returns the number of runs merged.
    """
    merged = 0
    have = {(r[0], r[1], r[2], r[3]) for r in dst.execute("SELECT label, condition, benchmark, config_hash FROM run")}
    for run in src.execute("SELECT * FROM run WHERE status='completed'").fetchall():
        cols = [d[0] for d in src.execute("SELECT * FROM run LIMIT 0").description]
        row = dict(zip(cols, run))
        if (row["label"], row["condition"], row["benchmark"], row["config_hash"]) in have:
            continue
        old = row.pop("run_id")
        new = dst.execute(f"INSERT INTO run({','.join(row)}) VALUES ({','.join('?' * len(row))})",
                          list(row.values())).lastrowid
        qcols = [d[0] for d in src.execute("SELECT * FROM query_log LIMIT 0").description]
        dcols = {r[1] for r in dst.execute("PRAGMA table_info(query_log)")}
        for q in src.execute("SELECT * FROM query_log WHERE run_id=?", (old,)).fetchall():
            qd = {k: v for k, v in zip(qcols, q) if k in dcols}
            oq = qd.pop("query_id")
            qd["run_id"] = new
            nq = dst.execute(f"INSERT INTO query_log({','.join(qd)}) VALUES ({','.join('?' * len(qd))})",
                             list(qd.values())).lastrowid
            dst.executemany("INSERT INTO score(query_id, metric, value) VALUES (?,?,?)",
                            [(nq, m, v) for m, v in src.execute("SELECT metric, value FROM score WHERE query_id=?", (oq,))])
        merged += 1
    dst.commit()
    return merged
