"""RunLogger (FR-13, NFR-08): one structured record per query, in the store file
(tables run / query_log / score / retrieved_note) and mirrored as JSONL under
``records/`` so every figure can be regenerated from logs alone (NFR-04).

This module deliberately does not import ``camr.memory``: evaluation must not
depend on engine internals (package diagram, Figure 4.6).  Retrieval data
arrives as plain dicts.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any

HARNESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS run (
    run_id        INTEGER PRIMARY KEY,
    label         TEXT NOT NULL,
    condition     TEXT NOT NULL CHECK (condition IN ('floor', 'ceiling', 'treatment')),
    benchmark     TEXT NOT NULL,
    task_type     TEXT NOT NULL,
    model_name    TEXT NOT NULL,
    model_version TEXT,
    config_json   TEXT NOT NULL,
    config_hash   TEXT NOT NULL,
    template_id   TEXT NOT NULL,
    seed          INTEGER NOT NULL,
    started_at    TIMESTAMP NOT NULL,
    finished_at   TIMESTAMP,
    status        TEXT NOT NULL DEFAULT 'running'
);
CREATE TABLE IF NOT EXISTS query_log (
    query_id            INTEGER PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES run(run_id),
    question_id         TEXT NOT NULL,
    dataset             TEXT NOT NULL,
    task_type           TEXT NOT NULL,
    question            TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('ok', 'failed')),
    error               TEXT,
    prompt              TEXT,
    context_tokens      INTEGER,
    prompt_tokens       INTEGER,
    generated_tokens    INTEGER,
    retrieval_latency_ms  REAL,
    generation_latency_ms REAL,
    e2e_latency_ms        REAL,
    budget              INTEGER,
    answer_text         TEXT,
    served_model        TEXT,
    logged_at           TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS score (
    score_id INTEGER PRIMARY KEY,
    query_id INTEGER NOT NULL REFERENCES query_log(query_id),
    metric   TEXT NOT NULL,
    value    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS retrieved_note (
    query_id         INTEGER NOT NULL REFERENCES query_log(query_id),
    note_id          INTEGER NOT NULL,
    rank             INTEGER NOT NULL,
    similarity       REAL NOT NULL,
    recency_score    REAL NOT NULL,
    importance_score REAL NOT NULL,
    composite_score  REAL NOT NULL,
    tokens           INTEGER NOT NULL,
    admitted         INTEGER NOT NULL,
    PRIMARY KEY (query_id, note_id)
);
CREATE INDEX IF NOT EXISTS idx_query_run       ON query_log(run_id);
CREATE INDEX IF NOT EXISTS idx_query_dataset   ON query_log(dataset);
CREATE INDEX IF NOT EXISTS idx_retrieved_query ON retrieved_note(query_id);
CREATE INDEX IF NOT EXISTS idx_retrieved_note  ON retrieved_note(note_id);
CREATE INDEX IF NOT EXISTS idx_score_query     ON score(query_id);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


class RunLogger:
    def __init__(self, conn: sqlite3.Connection, records_dir: str | Path | None = None):
        self.conn = conn
        self.conn.executescript(HARNESS_SCHEMA)
        self.conn.commit()
        self.records_dir = Path(records_dir) if records_dir else None
        if self.records_dir:
            self.records_dir.mkdir(parents=True, exist_ok=True)
        self._fh = None

    def start_run(
        self,
        *,
        label: str,
        condition: str,
        benchmark: str,
        task_type: str,
        model_name: str,
        model_version: str | None,
        config_json: str,
        config_hash: str,
        template_id: str,
        seed: int,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO run(label, condition, benchmark, task_type, model_name, model_version, config_json,"
            " config_hash, template_id, seed, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (label, condition, benchmark, task_type, model_name, model_version, config_json, config_hash,
             template_id, seed, _now()),
        )
        self.conn.commit()
        run_id = int(cur.lastrowid)
        if self.records_dir:
            self._fh = (self.records_dir / f"run_{run_id:04d}_{label}_{condition}_{benchmark}.jsonl").open("w")
            self._write({"type": "run", "run_id": run_id, "label": label, "condition": condition,
                         "benchmark": benchmark, "task_type": task_type, "model_name": model_name,
                         "model_version": model_version, "config": json.loads(config_json),
                         "config_hash": config_hash, "template_id": template_id, "seed": seed})
        return run_id

    def log_query(
        self,
        run_id: int,
        *,
        question_id: str,
        dataset: str,
        task_type: str,
        question: str,
        status: str,
        error: str | None = None,
        prompt: str | None = None,
        context_tokens: int | None = None,
        prompt_tokens: int | None = None,
        generated_tokens: int | None = None,
        retrieval_ms: float | None = None,
        generation_ms: float | None = None,
        e2e_ms: float | None = None,
        budget: int | None = None,
        answer: str | None = None,
        served_model: str | None = None,
        scores: dict[str, float] | None = None,
        retrieved: list[dict[str, Any]] | None = None,
    ) -> int:
        at = _now()
        cur = self.conn.execute(
            "INSERT INTO query_log(run_id, question_id, dataset, task_type, question, status, error, prompt,"
            " context_tokens, prompt_tokens, generated_tokens, retrieval_latency_ms, generation_latency_ms,"
            " e2e_latency_ms, budget, answer_text, served_model, logged_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, question_id, dataset, task_type, question, status, error, prompt, context_tokens,
             prompt_tokens, generated_tokens, retrieval_ms, generation_ms, e2e_ms, budget, answer,
             served_model, at),
        )
        qid = int(cur.lastrowid)
        if scores and status == "ok":
            self.conn.executemany(
                "INSERT INTO score(query_id, metric, value) VALUES (?,?,?)",
                [(qid, m, float(v)) for m, v in scores.items()],
            )
        if retrieved:
            self.conn.executemany(
                "INSERT INTO retrieved_note(query_id, note_id, rank, similarity, recency_score,"
                " importance_score, composite_score, tokens, admitted) VALUES (?,?,?,?,?,?,?,?,?)",
                [(qid, r["note_id"], r["rank"], r["similarity"], r["recency"], r["importance"],
                  r["composite"], r["tokens"], int(r["admitted"])) for r in retrieved],
            )
        self.conn.commit()
        self._write({"type": "query", "query_id": qid, "run_id": run_id, "question_id": question_id,
                     "dataset": dataset, "task_type": task_type, "status": status, "error": error,
                     "context_tokens": context_tokens, "prompt_tokens": prompt_tokens,
                     "generated_tokens": generated_tokens, "retrieval_latency_ms": retrieval_ms,
                     "generation_latency_ms": generation_ms, "e2e_latency_ms": e2e_ms, "budget": budget,
                     "answer_text": answer, "served_model": served_model, "scores": scores,
                     "retrieved": retrieved, "prompt": prompt, "logged_at": at})
        return qid

    def finish_run(self, run_id: int, status: str = "completed", model_version: str | None = None) -> None:
        if model_version:
            self.conn.execute("UPDATE run SET model_version=? WHERE run_id=?", (model_version, run_id))
        self.conn.execute("UPDATE run SET finished_at=?, status=? WHERE run_id=?", (_now(), status, run_id))
        self.conn.commit()
        self._write({"type": "end", "run_id": run_id, "status": status})
        if self._fh:
            self._fh.close()
            self._fh = None

    def _write(self, obj: dict[str, Any]) -> None:
        if self._fh:
            self._fh.write(json.dumps(obj, sort_keys=True, default=str) + "\n")
            self._fh.flush()
