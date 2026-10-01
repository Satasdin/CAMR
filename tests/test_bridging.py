"""Capability-adaptive mechanisms (docs/BRIDGING_THE_GAP.md): gating, entity-bridge
expansion, procedural (exemplar) memory, the ceiling_rag residual gap, and the
escalation curve."""

from __future__ import annotations

import sqlite3

import pytest

from camr.cli.commands import cmd_analyse
from camr.eval import RunLogger
from camr.eval.escalation import abstention_like, escalation_curve
from camr.harness import ExperimentRunner, LeakageError, Workspace, check_holdout, ingest, load_questions
from camr.harness.benchmarks import build_exemplars
from camr.memory import Document, HashingEmbedder, MemoryEngine, SQLiteVectorStore
from camr.memory.engine import _mentions

from conftest import FIXTURES, ScriptedRunner, fixture_config

BRIDGE_DOCS = [
    Document("hotpotqa", "Acme Rockets", "Acme Rockets is a launch company founded by Jane Holt in 1999.", "Acme Rockets"),
    Document("hotpotqa", "Jane Holt", "Jane Holt is an engineer who studied at the Massachusetts Institute of Technology.", "Jane Holt"),
    Document("hotpotqa", "Massachusetts Institute of Technology",
             "The Massachusetts Institute of Technology was established in 1861.", "Massachusetts Institute of Technology"),
    Document("hotpotqa", "Carmen", "Carmen is an opera by Georges Bizet first performed in 1875.", "Carmen"),
]


def _engine(cfg, store, embedder, tokenizer, **memory):
    return MemoryEngine.from_config(cfg.with_overrides({"memory": memory}), store=store, embedder=embedder,
                                    tokenizer=tokenizer)


# ------------------------------------------------------------------ gating
def test_abstains_when_nothing_relevant(cfg, store, embedder, tokenizer):
    eng = _engine(cfg, store, embedder, tokenizer, min_similarity=0.99)
    eng.ingest(BRIDGE_DOCS)
    r = eng.recall("Who painted the Mona Lisa?")
    assert r.abstained and r.context == "" and r.context_tokens == 0
    assert r.top_similarity is not None and not any(c.admitted for c in r.candidates)


def test_margin_makes_the_budget_a_ceiling(cfg, store, embedder, tokenizer):
    eng = _engine(cfg, store, embedder, tokenizer, similarity_margin=0.0)
    eng.ingest(BRIDGE_DOCS)
    full = _engine(cfg, store, embedder, tokenizer)
    r_gated, r_full = eng.recall("When was Carmen first performed?"), full.recall("When was Carmen first performed?")
    assert [c.note.text for c in r_gated.admitted] == [r_full.admitted[0].note.text]
    assert r_gated.context_tokens < r_full.context_tokens and not r_gated.abstained


# --------------------------------------------------------------- expansion
def test_mentions_prefers_longest_match_and_aliases():
    index = {"Jane Holt": [1], "Jane": [9], "Titanic": [2], "Massachusetts Institute of Technology": [3]}
    text = "Directed after Titanic, Jane Holt studied at the Massachusetts Institute of Technology."
    assert _mentions(text, index, 4) == ["Titanic", "Jane Holt", "Massachusetts Institute of Technology"]
    assert _mentions("Janet Holtz", index, 4) == []


def test_entity_bridge_reaches_the_second_hop(cfg, store, embedder, tokenizer):
    q = "In what year was the university attended by the founder of Acme Rockets established?"
    plain = _engine(cfg, store, embedder, tokenizer, k=1)
    plain.ingest(BRIDGE_DOCS)
    assert "Jane Holt is" not in plain.recall(q).context

    bridged = _engine(cfg, store, embedder, tokenizer, k=1, expansion="entity", expansion_seeds=2)
    r = bridged.recall(q)
    texts = [c.note.text for c in r.admitted]
    assert texts[0].startswith("Acme Rockets") and texts[1].startswith("Jane Holt")
    assert r.candidates[1].via == r.candidates[0].note.note_id
    assert r.timings["expand_ms"] < 50


def test_titles_survive_a_store_written_before_the_column_existed(tmp_path, embedder):
    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE source (source_id INTEGER PRIMARY KEY, dataset TEXT NOT NULL, doc_id TEXT NOT NULL,"
                 " note_type TEXT NOT NULL, ingested_at TIMESTAMP NOT NULL, screener_verdict TEXT,"
                 " UNIQUE (dataset, doc_id, note_type))")
    conn.commit()
    conn.close()
    s = SQLiteVectorStore(db, dim=embedder.dim, embedder_name=embedder.name, use_vec=False)
    assert "title" in {r[1] for r in s.conn.execute("PRAGMA table_info(source)")}


# ------------------------------------------------------- procedural memory
def _exemplar_cfg(tmp_path, mode):
    return fixture_config(tmp_path).with_overrides({
        "memory": {"reasoning_memory": mode},
        "benchmarks": {"gsm8k": {"exemplars": str(FIXTURES / "gsm8k_train.jsonl")}},
    })


def _ws(cfg, local=None, cloud=None):
    return Workspace(cfg, local_runner=local or ScriptedRunner("local"),
                     ceiling_runner=cloud or ScriptedRunner("cloud", remote=True),
                     embedder=HashingEmbedder(cfg.embedder.dim))


def test_reasoning_uses_exemplar_memory(tmp_path):
    cfg = _exemplar_cfg(tmp_path, "exemplars")
    local = ScriptedRunner("local")
    ws = _ws(cfg, local)
    ingest(ws)
    assert ws.store.count("exemplar") == 4
    ExperimentRunner(ws).run("treatment", "gsm8k")
    assert all(p.startswith("Here are solved examples") for p in local.prompts)
    assert all("Solution:" in p and "#### " in p for p in local.prompts)


def test_reasoning_memory_none_is_identical_to_floor(tmp_path):
    cfg = _exemplar_cfg(tmp_path, "none")
    local = ScriptedRunner("local")
    ws = _ws(cfg, local)
    ingest(ws)
    runner = ExperimentRunner(ws)
    runner.run("floor", "gsm8k")
    floor_prompts = list(local.prompts)
    local.prompts.clear()
    runner.run("treatment", "gsm8k")
    assert local.prompts == floor_prompts


def test_exemplars_are_held_out_from_the_test_sample():
    test_qs = load_questions("gsm8k", FIXTURES / "gsm8k.jsonl")
    from camr.config import BenchmarkConfig
    ex = build_exemplars(BenchmarkConfig(path="", exemplars=str(FIXTURES / "gsm8k_train.jsonl")))
    check_holdout(ex, test_qs)
    leaked = build_exemplars(BenchmarkConfig(path="", exemplars=str(FIXTURES / "gsm8k.jsonl")))
    with pytest.raises(LeakageError):
        check_holdout(leaked, test_qs)


# ------------------------------------------------------ residual gap (P2)
POPQA = {"Kithuku": "botanist", "Ondiri": "Kenya", "Zeta": "jazz", "Loolmalasin": "Tanzania"}


def _q(p):
    return p.rsplit("Question:", 1)[-1]


def test_ceiling_rag_measures_the_residual_gap(tmp_path):
    cfg = fixture_config(tmp_path).with_overrides({"extra_conditions": ["ceiling_rag"]})
    # Small model: answers only half the questions even with the fact in front of it (a reading gap).
    def small(p):
        if "Notes:" not in p:
            return "unknown"
        return next((a for s, a in POPQA.items() if s in _q(p) and s in ("Kithuku", "Ondiri")), "unknown")
    def large(p):
        return next((a for s, a in POPQA.items() if s in _q(p) and ("Notes:" in p or s == "Kithuku")), "unknown")
    cloud = ScriptedRunner("cloud", respond=large, remote=True)
    ws = _ws(cfg, ScriptedRunner("local", respond=small), cloud)
    ingest(ws)
    runner = ExperimentRunner(ws)
    for cond in ("floor", "ceiling", "treatment", "ceiling_rag"):
        runner.run(cond, "popqa")
    assert sum("Notes:" in p for p in cloud.prompts) == 4  # ceiling_rag got the notes, ceiling did not
    ws.close()
    [r] = cmd_analyse(ws.run_dir, cfg=cfg)["main"]
    assert (r["floor"], r["ceiling"], r["treatment"], r["ceiling_rag"]) == (0.0, 0.25, 0.5, 1.0)
    assert r["residual_gap"] == pytest.approx(0.5)  # what scale still buys when knowledge is equal
    assert r["n_ceiling_rag"] == 4


# ------------------------------------------------------ escalation (P6)
def _log(conn, cond, answers_scores, task="single_hop", bench="popqa"):
    lg = RunLogger(conn)
    rid = lg.start_run(label="main", condition=cond, benchmark=bench, task_type=task, model_name="m",
                       model_version=None, config_json="{}", config_hash="h", template_id="t", seed=1)
    for i, (ans, score, sim) in enumerate(answers_scores):
        lg.log_query(rid, question_id=str(i), dataset=bench, task_type=task, question="q", status="ok", answer=ans,
                     top_similarity=sim, scores={"contains": score})
    lg.finish_run(rid)


def test_escalation_curve_endpoints_and_router_ordering():
    conn = sqlite3.connect(":memory:")
    n = 10
    _log(conn, "floor", [("x", 0.0, None)] * n)
    _log(conn, "ceiling", [("x", 1.0, None)] * n)
    # Treatment: right on 6 confident queries, wrong on 4 (two say "unknown", two low-similarity guesses).
    treat = [("ans", 1.0, 0.9)] * 6 + [("unknown", 0.0, 0.8), ("I don't know", 0.0, 0.7),
                                       ("guess", 0.0, 0.2), ("guess", 0.0, 0.3)]
    _log(conn, "treatment", treat)
    curve = {r["escalation_rate"]: r for r in escalation_curve(conn, {"popqa": "contains"}, rates=(0, 0.2, 0.4, 1.0))}
    assert curve[0.0]["gap_closed"] == pytest.approx(0.6)
    assert curve[1.0]["gap_closed"] == pytest.approx(1.0)
    assert curve[0.4]["gap_closed"] == pytest.approx(1.0)  # confidence finds all four misses
    assert curve[0.4]["gap_closed_oracle_router"] == pytest.approx(1.0)
    assert curve[0.4]["gap_closed_random_router"] == pytest.approx(0.6 + 0.4 * 0.4)
    assert curve[0.2]["on_device_share"] == pytest.approx(0.8)


def test_abstention_detection():
    assert abstention_like("Unknown.") and abstention_like("") and abstention_like("I don't know")
    assert not abstention_like("Kenya") and not abstention_like("Known for jazz")


# ------------------------------------------------------ memory growth over time
def test_growth_accumulates_knowledge_with_a_frozen_model(tmp_path):
    from camr.harness.growth import run_growth
    cfg = fixture_config(tmp_path).with_overrides({"benchmarks": {
        "popqa": {"path": str(FIXTURES / "popqa.jsonl"), "corpus": str(FIXTURES / "popqa_corpus.jsonl"), "n": 4}}})
    cfg.benchmarks = {"popqa": cfg.benchmarks["popqa"]}
    def reader(p):  # answers only when a note about the subject is in context
        notes = p.split("Notes:", 1)[1].split("Question:", 1)[0] if "Notes:" in p else ""
        return next((a for s, a in POPQA.items() if s in _q(p) and s in notes), "unknown")
    ws = _ws(cfg, ScriptedRunner("local", respond=reader), ScriptedRunner("cloud", respond=lambda p: next(
        (a for s, a in POPQA.items() if s in _q(p)), "unknown"), remote=True))
    rows = run_growth(ws, cfg, [0.25, 0.5, 1.0])
    notes = [r["notes_in_population"] for r in rows]
    acc = [r["accuracy"] for r in rows]
    assert notes == sorted(notes) and notes[0] < notes[-1]       # the store grows stage by stage
    assert acc == sorted(acc) and acc[-1] == 1.0                   # knowledge accrues: accuracy never falls
    assert [r["stage"] for r in rows] == ["grow-025", "grow-050", "grow-100"]
