"""Failure decomposition for knowledge-bound questions.

For each treatment run, each question is placed at the first stage where the
gold answer is lost:

    store      the answer string appears in some note of the population
    candidates it appears in one of the k retrieved candidates
    context    it appears in an admitted (in-budget) note
    correct    the model's answer scored correct

``in_store`` < 1 implicates the write policy (distillation dropped the fact),
a drop from store to candidates implicates the embedder / k, a drop from
candidates to context implicates ranking or the budget, and a drop from context
to correct implicates the frozen model's reading.  This turns the Query Trace
screen's single-question diagnosis into a table over the whole sample.

String containment is a lower bound (paraphrases are missed), so the numbers
are indicative of where losses occur rather than exact.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from camr.eval.scoring import normalize_answer
from camr.harness.benchmarks import Question


def _contains(haystack: str, golds: list[str]) -> bool:
    h = f" {normalize_answer(haystack)} "
    return any(normalize_answer(g) and f" {normalize_answer(g)} " in h for g in golds)


def coverage(conn: sqlite3.Connection, samples: dict[str, list[Question]], primary_metric: dict[str, str]) -> list[dict]:
    runs = conn.execute(
        "SELECT r.run_id, r.label, r.benchmark, json_extract(r.config_json, '$.memory.write_policy'),"
        " json_extract(r.config_json, '$.memory.screening') FROM run r"
        " WHERE r.condition='treatment' AND r.status='completed' AND r.label NOT LIKE 'profile%'"
        " AND r.run_id IN (SELECT MAX(run_id) FROM run GROUP BY label, condition, benchmark)"
    ).fetchall()
    note_cache: dict[str, list[str]] = {}
    out = []
    for run_id, label, bench, write_policy, screening in runs:
        if bench not in samples or bench == "gsm8k":
            continue
        note_type = write_policy + ("" if screening else "-unscreened")
        if note_type not in note_cache:
            note_cache[note_type] = [r[0] for r in conn.execute("SELECT text FROM note WHERE note_type=?", (note_type,))]
        store_texts = note_cache[note_type]
        by_qid = {q.qid: q for q in samples[bench]}
        metric = primary_metric.get(bench, "em")
        counts = defaultdict(int)
        n = 0
        for qid, query_id, status in conn.execute(
            "SELECT question_id, query_id, status FROM query_log WHERE run_id=?", (run_id,)
        ):
            q = by_qid.get(qid)
            if q is None or status != "ok":
                continue
            n += 1
            cands = conn.execute(
                "SELECT n.text, rn.admitted FROM retrieved_note rn JOIN note n USING(note_id) WHERE rn.query_id=?",
                (query_id,),
            ).fetchall()
            in_store = any(_contains(t, q.answers) for t in store_texts)
            in_cands = any(_contains(t, q.answers) for t, _ in cands)
            in_ctx = any(_contains(t, q.answers) for t, a in cands if a)
            s = conn.execute("SELECT value FROM score WHERE query_id=? AND metric=?", (query_id, metric)).fetchone()
            counts["in_store"] += in_store
            counts["in_candidates"] += in_cands
            counts["in_context"] += in_ctx
            counts["correct"] += bool(s and s[0] > 0)
            counts["correct_given_context"] += bool(in_ctx and s and s[0] > 0)
        if n:
            out.append({
                "label": label,
                "benchmark": bench,
                "note_type": note_type,
                "n": n,
                "answer_in_store": counts["in_store"] / n,
                "answer_in_candidates": counts["in_candidates"] / n,
                "answer_in_context": counts["in_context"] / n,
                "correct": counts["correct"] / n,
                "correct_when_in_context": (counts["correct_given_context"] / counts["in_context"])
                if counts["in_context"] else None,
            })
    out.sort(key=lambda r: (r["benchmark"], r["label"]))
    return out
