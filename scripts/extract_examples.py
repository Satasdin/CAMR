"""Pull worked examples for the report straight from the benchmark logs (nothing retyped).

Each example keeps the question, the gold answer, what each condition was given (prompt excerpt
and admitted notes with their similarity and how they were reached) and what it answered.

    python scripts/extract_examples.py --out docs/results/examples.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT, H200 = ROOT / "results/pilot/camr.sqlite", ROOT / "results/hotpot200/camr.sqlite"


def ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def answer(c, run_id, qid, metric):
    row = c.execute("SELECT q.query_id, q.answer_text, q.prompt, q.prompt_tokens, q.e2e_latency_ms, s.value FROM query_log q"
                    " LEFT JOIN score s ON s.query_id=q.query_id AND s.metric=? WHERE q.run_id=? AND q.question_id=?",
                    (metric, run_id, qid)).fetchone()
    model = c.execute("SELECT model_name FROM run WHERE run_id=?", (run_id,)).fetchone()[0]
    return {"model": model, "query_id": row[0], "answer": row[1], "prompt": row[2], "prompt_tokens": row[3],
            "seconds": round((row[4] or 0) / 1000, 1), "correct": row[5]}


def trace(c, query_id):
    q = ("SELECT r.rank, r.similarity, r.admitted, r.via_note_id, r.tokens, n.text, s.title FROM retrieved_note r"
         " JOIN note n USING(note_id) JOIN source s USING(source_id) WHERE r.query_id=? ORDER BY r.admitted DESC, r.rank")
    return [{"rank": rk, "similarity": round(sim, 3), "admitted": bool(ad), "via_bridge": via is not None, "tokens": tok,
             "title": title, "text": text} for rk, sim, ad, via, tok, text, title in c.execute(q, (query_id,))]


def gold(bench, qid):
    if bench == "gsm8k":
        from camr.harness.benchmarks import load_questions
        return next(q.answers[0] for q in load_questions("gsm8k", ROOT / "data/gsm8k/test.jsonl") if q.qid == qid)
    from camr.harness.benchmarks import load_questions
    src = {"hotpotqa": ROOT / "data/hotpotqa/hotpot_dev_distractor_v1.json", "popqa": ROOT / "data/popqa/test.tsv"}[bench]
    return next(q.answers for q in load_questions(bench, src) if q.qid == qid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs/results/examples.json"))
    a = ap.parse_args()
    p, h = ro(PILOT), ro(H200)
    ex = {}
    # Maths: the same problem with and without worked-example memory, two model sizes, and the cloud model.
    qid = "gsm8k-00189"
    ex["maths_helps"] = {"bench": "gsm8k", "qid": qid, "gold": gold("gsm8k", qid), "conditions": {
        "phi4-mini:3.8b alone": answer(p, 125, qid, "accuracy"),
        "phi4-mini:3.8b + CAMR worked examples": answer(p, 126, qid, "accuracy"),
        "qwen2.5:14b alone": answer(p, 149, qid, "accuracy"),
        "qwen2.5:14b + CAMR worked examples": answer(p, 150, qid, "accuracy"),
        "qwen2.5:0.5b + CAMR worked examples": answer(p, 32, qid, "accuracy"),
        "Kimi K3 (cloud)": answer(p, 18, qid, "accuracy")}}
    qid = "gsm8k-00108"
    ex["maths_hurts"] = {"bench": "gsm8k", "qid": qid, "gold": gold("gsm8k", qid), "conditions": {
        "qwen2.5:0.5b alone": answer(p, 30, qid, "accuracy"),
        "qwen2.5:0.5b + CAMR worked examples": answer(p, 32, qid, "accuracy")}}
    # Long-tail fact (single hop): the pilot's first logged example.
    qid = "4087381"
    ex["fact"] = {"bench": "popqa", "qid": qid, "gold": gold("popqa", qid), "conditions": {
        "qwen2.5:0.5b alone": answer(p, 19, qid, "contains"),
        "qwen2.5:0.5b + CAMR": answer(p, 21, qid, "contains"),
        "gpt-oss:20b alone": answer(p, 20, qid, "contains"),
        "Kimi K3 (cloud)": answer(p, c_run(p, "kimi", "ceiling", "popqa"), qid, "contains")}}
    ex["fact"]["trace"] = trace(p, ex["fact"]["conditions"]["qwen2.5:0.5b + CAMR"]["query_id"])
    # Multi-hop with entity bridging, n = 200 run (llama3.2:3b), alone vs with CAMR, and the cloud model.
    for key, qid in (("bridge_1", "5abe239355429976d4830a7d"), ("bridge_2", "5a7b88a85542995eb53be954")):
        ex[key] = {"bench": "hotpotqa", "qid": qid, "gold": gold("hotpotqa", qid), "conditions": {
            "llama3.2:3b alone": answer(h, 5, qid, "em"),
            "llama3.2:3b + CAMR": answer(h, 6, qid, "em"),
            "Kimi K3 (cloud), closed book": answer(h, 9, qid, "em")}}
        ex[key]["trace"] = trace(h, ex[key]["conditions"]["llama3.2:3b + CAMR"]["query_id"])
    for e in ex.values():
        e["question"] = p.execute("SELECT question FROM query_log WHERE question_id=? LIMIT 1", (e["qid"],)).fetchone() or \
            h.execute("SELECT question FROM query_log WHERE question_id=? LIMIT 1", (e["qid"],)).fetchone()
        e["question"] = e["question"][0]
    Path(a.out).write_text(json.dumps(ex, indent=2, ensure_ascii=False))
    for k, e in ex.items():
        print(k, e["question"][:70], {n: c["correct"] for n, c in e["conditions"].items()})


def c_run(c, label, cond, bench):
    return c.execute("SELECT MAX(run_id) FROM run WHERE label=? AND condition=? AND benchmark=? AND status='completed'",
                     (label, cond, bench)).fetchone()[0]


if __name__ == "__main__":
    main()
