"""Read-only queries behind the inspection interface (FR-17, IR-06).

The database is opened with SQLite's ``mode=ro`` URI flag, so the interface is
read-only by construction rather than by convention: any write attempt fails
at the driver.  Nothing here imports a model runner or the engine's write path.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def connect_ro(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, "SELECT run_id, label, condition, benchmark, task_type, model_name, model_version,"
                       " config_hash, template_id, started_at, finished_at, status FROM run ORDER BY run_id")


def run_summary(conn: sqlite3.Connection, label: str) -> list[dict[str, Any]]:
    """Per-condition token and latency aggregates for one label (plus the main floor/ceiling)."""
    return _rows(conn, """
        SELECT r.condition, r.benchmark, COUNT(*) AS questions,
               SUM(q.status = 'failed') AS failed,
               AVG(q.context_tokens) AS mean_context_tokens,
               AVG(q.prompt_tokens) AS mean_prompt_tokens,
               AVG(q.retrieval_latency_ms) AS mean_retrieval_ms,
               AVG(q.generation_latency_ms) AS mean_generation_ms,
               AVG(q.e2e_latency_ms) AS mean_e2e_ms
        FROM query_log q JOIN run r USING(run_id)
        WHERE r.status = 'completed' AND (r.label = ? OR (r.label = 'main' AND r.condition != 'treatment'))
          AND r.run_id IN (SELECT MAX(run_id) FROM run GROUP BY label, condition, benchmark)
        GROUP BY r.condition, r.benchmark ORDER BY r.benchmark, r.condition
    """, (label,))


def questions(conn: sqlite3.Connection, run_id: int) -> list[dict[str, Any]]:
    return _rows(conn, "SELECT query_id, question_id, dataset, question, status FROM query_log"
                       " WHERE run_id=? ORDER BY query_id", (run_id,))


def query_trace(conn: sqlite3.Connection, dataset: str, question_id: str, label: str = "main") -> dict[str, Any]:
    """Answers under every condition, scores, and the full retrieval record (Figure 4.12)."""
    answers = _rows(conn, """
        SELECT r.run_id, r.label, r.condition, r.model_name, q.query_id, q.status, q.error, q.answer_text,
               q.context_tokens, q.prompt_tokens, q.budget, q.prompt, q.retrieval_latency_ms,
               q.generation_latency_ms, q.e2e_latency_ms
        FROM query_log q JOIN run r USING(run_id)
        WHERE q.dataset=? AND q.question_id=? AND (r.label=? OR (r.label='main' AND r.condition!='treatment'))
          AND r.run_id IN (SELECT MAX(run_id) FROM run GROUP BY label, condition, benchmark)
        ORDER BY CASE r.condition WHEN 'floor' THEN 0 WHEN 'treatment' THEN 1 ELSE 2 END
    """, (dataset, question_id, label))
    for a in answers:
        a["scores"] = {r["metric"]: r["value"] for r in _rows(
            conn, "SELECT metric, value FROM score WHERE query_id=?", (a["query_id"],))}
    trace: list[dict[str, Any]] = []
    treat = next((a for a in answers if a["condition"] == "treatment"), None)
    if treat:
        trace = _rows(conn, """
            SELECT rn.rank, rn.note_id, rn.similarity, rn.recency_score, rn.importance_score,
                   rn.composite_score, rn.tokens, rn.admitted, n.text, n.note_type, s.dataset AS source_dataset,
                   s.doc_id AS source_doc
            FROM retrieved_note rn
            LEFT JOIN note n USING(note_id) LEFT JOIN source s ON s.source_id = n.source_id
            WHERE rn.query_id=? ORDER BY rn.rank
        """, (treat["query_id"],))
    return {"answers": answers, "trace": trace}


def note_types(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT note_type FROM note ORDER BY 1")]


def store_overview(conn: sqlite3.Connection, note_type: str) -> dict[str, Any]:
    """Figure 4.13 headline numbers.  'Ever retrieved' comes from the retrieval log,
    not access counters, because access state is reset at the start of each run."""
    n, mean_tok = conn.execute("SELECT COUNT(*), AVG(token_count) FROM note WHERE note_type=?",
                               (note_type,)).fetchone()
    rej = conn.execute("SELECT COUNT(*) FROM rejection WHERE note_type=?", (note_type,)).fetchone()[0]
    has_log = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='retrieved_note'").fetchone()[0]
    retrieved = 0
    if has_log:
        retrieved = conn.execute(
            "SELECT COUNT(DISTINCT rn.note_id) FROM retrieved_note rn JOIN note n USING(note_id)"
            " WHERE n.note_type=? AND rn.admitted=1", (note_type,)).fetchone()[0]
    return {
        "notes": n,
        "mean_note_tokens": mean_tok or 0.0,
        "rejections": rej,
        "ingestion_yield": n / (n + rej) if (n + rej) else None,
        "never_retrieved": n - retrieved,
        "never_retrieved_share": (n - retrieved) / n if n else None,
    }


def notes(conn: sqlite3.Connection, note_type: str, dataset: str | None = None,
          never_retrieved: bool = False, limit: int = 500) -> list[dict[str, Any]]:
    has_log = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='retrieved_note'").fetchone()[0]
    times = ("(SELECT COUNT(*) FROM retrieved_note rn WHERE rn.note_id=n.note_id AND rn.admitted=1)"
             if has_log else "0")
    sql = (f"SELECT n.note_id, n.text, n.token_count, n.importance, n.created_at, n.last_accessed_at,"
           f" n.access_count, {times} AS times_admitted, s.dataset, s.doc_id, s.screener_verdict"
           f" FROM note n JOIN source s USING(source_id) WHERE n.note_type=?")
    args: list[Any] = [note_type]
    if dataset:
        sql += " AND s.dataset=?"
        args.append(dataset)
    if never_retrieved:
        sql += f" AND {times} = 0"
    sql += " ORDER BY n.note_id LIMIT ?"
    args.append(limit)
    return _rows(conn, sql, tuple(args))


def rejections(conn: sqlite3.Connection, note_type: str, limit: int = 200) -> list[dict[str, Any]]:
    return _rows(conn, "SELECT r.reason, r.text, s.dataset, s.doc_id FROM rejection r"
                       " LEFT JOIN source s USING(source_id) WHERE r.note_type=? ORDER BY r.rejection_id LIMIT ?",
                 (note_type, limit))
