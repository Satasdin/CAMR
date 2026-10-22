"""Engine bench scoring (camr.eval.abilities): pass rules, miss reasons, LongMemEval needed facts, sampling, summaries."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from camr.eval.abilities import (Cand, Spec, gate_precision, has_date, lme_date, lme_spec, miss_reason, score,
                                 scorecard, stratified_sample, summarise, tell_apart, update_cue, wilson)

FIXTURE = Path(__file__).parent / "fixtures" / "engine_bench" / "camr_scenarios.json"


def c(keys=(), tokens=10, text="", admitted=True, eligible=True, rank=1, sim=0.7):
    return Cand(frozenset(keys), tokens, text, sim, rank, eligible, admitted)


def run(spec, cands, abstained=False, top=0.7):
    return score(spec, cands, abstained=abstained, retrieval_ms=12.5, top_similarity=top, min_similarity=0.5)


# ---------------------------------------------------------------------- rule "all"
def test_all_needed_passes_only_when_every_group_reaches_the_context():
    spec = Spec("q", "A2", "s", "join?", needed=[{"a1", "a2"}, {"b"}])
    both = run(spec, [c(["a2"]), c(["b"])])
    assert both["passed"] and both["all_needed"] and both["reached"] == 2
    one = run(spec, [c(["a1"]), c(["b"], admitted=False, rank=2)])
    assert not one["passed"] and one["reached"] == 1 and one["all_needed"] is False


def test_distractor_share_is_by_tokens_and_zero_for_an_empty_context():
    spec = Spec("q", "A1", "s", "?", needed=[{"a"}])
    r = run(spec, [c(["a"], tokens=30), c([], tokens=60), c(["other"], tokens=10)])
    assert r["distractor_share"] == pytest.approx(0.7) and r["context_tokens"] == 100 and r["admitted"] == 3
    empty = run(spec, [c(["a"], admitted=False)], abstained=True)
    assert empty["distractor_share"] == 0.0 and empty["context_tokens"] == 0


# ---------------------------------------------------------------------- rule "newest" (A3)
def test_knowledge_update_needs_the_newest_value_and_a_way_to_tell_it_from_the_old_one():
    spec = Spec("q", "A3", "s", "Which floor?", needed=[{"new"}], stale={"old"}, rule="newest")
    assert run(spec, [c(["new"], text="My office is on the 5th floor.")])["passed"]  # alone: nothing to confuse
    plain = run(spec, [c(["old"], text="My office is on the 3rd floor."), c(["new"], text="My office is on the 5th floor.")])
    assert not plain["passed"] and plain["stale_in_context"] and plain["stale_first"]
    cue = run(spec, [c(["new"], text="Update: my office moved to the 5th floor."), c(["old"], text="3rd floor.")])
    assert cue["passed"] and not cue["stale_first"]
    dated = run(spec, [c(["old"], text="On 2023-05-01 the user said: 3rd floor"),
                       c(["new"], text="On 2023-06-01 the user said: 5th floor")])
    assert dated["passed"]
    wrong_way = run(spec, [c(["old"], text="On 2023-07-01 the user said: 3rd floor"),
                           c(["new"], text="On 2023-06-01 the user said: 5th floor")])
    assert not wrong_way["passed"]
    assert not run(spec, [c(["old"], text="Update: 3rd floor")])["passed"]  # the newest never arrived


# ---------------------------------------------------------------------- rule "temporal" (A4)
def test_temporal_needs_dated_needed_notes_and_nothing_from_outside_the_period():
    spec = Spec("q", "A4", "s", "What did the electrician fix last week?", needed=[{"oct"}], out_of_window={"sep"},
                rule="temporal")
    assert run(spec, [c(["oct"], text="On 2026-10-13 the user said: kitchen socket")])["passed"]
    assert not run(spec, [c(["oct"], text="The electrician fixed the kitchen socket")])["passed"]  # no date shown
    both = run(spec, [c(["oct"], text="On 2026-10-13 ..."), c(["sep"], text="On 2026-09-02 ...")])
    assert not both["passed"] and both["out_of_window_in_context"]


# ---------------------------------------------------------------------- abstain and no_harm
def test_abstain_and_no_harm_rules():
    abst = Spec("q", "A7", "s", "What is my blood type?", rule="abstain")
    assert run(abst, [c(admitted=False, eligible=False)], abstained=True, top=0.42)["passed"]
    opened = run(abst, [c(tokens=40)], abstained=False, top=0.55)
    assert not opened["passed"] and opened["distractor_share"] == 1.0 and opened["all_needed"] is None
    harm = Spec("q", "A10", "s", "Who wrote Things Fall Apart?", rule="no_harm")
    assert run(harm, [], abstained=False)["passed"]  # empty context, even without abstaining
    assert not run(harm, [c(tokens=5)])["passed"]
    with pytest.raises(ValueError):
        Spec("q", "A1", "s", "?", rule="maybe")


# ---------------------------------------------------------------------- why a needed fact was missed
def test_miss_reasons_follow_the_read_path():
    g = frozenset({"a"})
    assert miss_reason(g, [c(["x"])], abstained=False, top_similarity=0.7, min_similarity=0.5) == "not retrieved"
    lost = [c(["a"], admitted=False, eligible=False, rank=3)]
    assert miss_reason(g, lost, abstained=True, top_similarity=0.45, min_similarity=0.5) == "similarity gate"
    assert miss_reason(g, lost, abstained=True, top_similarity=0.62, min_similarity=0.5) == "entity gate"
    assert miss_reason(g, lost, abstained=False, top_similarity=0.8, min_similarity=0.5) == "below margin"
    full = [c(["a"], admitted=False, eligible=True, rank=4)]
    assert miss_reason(g, full, abstained=False, top_similarity=0.8, min_similarity=0.5) == "budget full"
    rec = run(Spec("q", "A5", "s", "How many?", needed=[{"a"}, {"b"}]), [c(["b"]), *full])
    assert rec["misses"] == ["budget full"]


# ---------------------------------------------------------------------- dates and cues
def test_dates_and_update_cues():
    assert has_date("On 2026-10-13 the user said: hi") and has_date("due on 5 May") and has_date("on March 3rd")
    assert not has_date("My office is on the 5th floor of Delta House.")
    assert lme_date("2023/05/20 (Sat) 02:21") == "2023-05-20"
    assert update_cue("Update: my office moved") and update_cue("I no longer eat meat")
    assert not update_cue("The gym membership costs 5,200 shillings a month from October.")
    assert tell_apart([c(text="On 2024-01-02 x")], [c(text="On 2023-12-31 y")])
    assert not tell_apart([c(text="x")], [c(text="y")])


# ---------------------------------------------------------------------- LongMemEval
def _lme(qid="q1", qtype="multi-session", answer_ids=("s1", "s2"), flags=True):
    t = (lambda text, ans=False: {"role": "user", "content": text, **({"has_answer": True} if ans and flags else {})})
    return {"question_id": qid, "question_type": qtype, "question": "How many?", "answer": 2,
            "answer_session_ids": list(answer_ids),
            "haystack_session_ids": ["s0", "s1", "s2"],
            "haystack_dates": ["2023/05/01 (Mon) 10:00", "2023/05/20 (Sat) 09:00", "2023/05/10 (Wed) 08:00"],
            "haystack_sessions": [[t("noise")], [t("hi"), t("I bought a bike", True)], [t("I bought a car", True), t("ok")]]}


def test_lme_needed_facts_are_flagged_turns_per_evidence_session():
    spec = lme_spec(_lme())
    assert spec.ability == "A2" and spec.suite == "lme-ms" and spec.rule == "all"
    assert sorted(map(sorted, spec.needed)) == [["s1#1"], ["s2#0"]]
    unflagged = lme_spec(_lme(flags=False))  # no flags in a session: any of its turns counts
    assert sorted(map(sorted, unflagged.needed)) == [["s1#0", "s1#1"], ["s2#0", "s2#1"]]
    assert unflagged.meta["unflagged_sessions"] == 2


def test_lme_knowledge_update_needs_the_newest_session_and_abstention_is_a7():
    ku = lme_spec(_lme(qtype="knowledge-update"))
    assert ku.rule == "newest" and ku.needed == [frozenset({"s1#1"})] and ku.stale == {"s2#0"}  # s1 is 2023-05-20
    assert lme_spec(_lme(qtype="temporal-reasoning")).rule == "temporal"
    assert lme_spec(_lme(qtype="single-session-assistant")).ability == "A1"
    abs_ = lme_spec(_lme(qid="q1_abs"))
    assert abs_.ability == "A7" and abs_.rule == "abstain" and not abs_.needed


def test_stratified_sample_is_seeded_capped_and_keeps_order():
    items = [{"id": i, "g": "a" if i % 3 else "b"} for i in range(30)]
    one = stratified_sample(items, lambda x: x["g"], 5, seed=13)
    assert one == stratified_sample(items, lambda x: x["g"], 5, seed=13)
    assert sum(x["g"] == "a" for x in one) == 5 and sum(x["g"] == "b" for x in one) == 5
    assert [x["id"] for x in one] == sorted(x["id"] for x in one)
    assert len(stratified_sample(items, lambda x: x["g"], 50, seed=1)) == 30
    assert stratified_sample(items, lambda x: x["g"], 5, seed=14) != one


# ---------------------------------------------------------------------- summaries
def test_wilson_interval():
    assert wilson(0, 0) is None
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert wilson(10, 10)[1] == 1.0


def test_summary_gate_precision_and_scorecard():
    recs = [
        {"ability": "A1", "suite": "x", "rule": "all", "passed": True, "all_needed": True, "abstained": False,
         "retrieval_ms": 10.0, "context_tokens": 100, "distractor_share": 0.5},
        {"ability": "A1", "suite": "y", "rule": "all", "passed": False, "all_needed": False, "abstained": True,
         "retrieval_ms": 30.0, "context_tokens": 0, "distractor_share": 0.0, "misses": ["entity gate"]},
        {"ability": "A7", "suite": "z", "rule": "abstain", "passed": False, "all_needed": None, "abstained": False,
         "retrieval_ms": 20.0, "context_tokens": 50, "distractor_share": 1.0},
        {"ability": "A8", "suite": "forget", "passed": True},
    ]
    s = summarise(recs[:2])
    assert s["n"] == 2 and s["pass_rate"] == 0.5 and s["all_needed_recall"] == 0.5 and s["misses"] == {"entity gate": 1}
    assert s["retrieval_ms_median"] == 10.0 and s["retrieval_ms_p95"] == 30.0 and s["abstain_rate"] == 0.5
    g = gate_precision(recs)
    assert g["opened_answerable"] == 1 and g["opened_unanswerable"] == 1 and g["precision"] == 0.5
    assert g["specificity"] == 0.0 and g["sensitivity"] == 0.5
    card = scorecard(recs)
    assert set(card) == {f"A{i}" for i in range(1, 11)}
    assert card["A10"]["n"] == 1 and "A7 z" in card["A10"]["suites"]  # A7's questions count for do-no-harm
    assert card["A8"]["pass_rate"] == 1.0 and card["A8"]["abstain_rate"] is None
    assert card["A3"]["n"] == 0 and card["A3"]["pass_rate"] is None


# ---------------------------------------------------------------------- the fixture and the bench's glue
def test_scenario_fixture_is_consistent():
    fx = json.loads(FIXTURE.read_text())
    ids = {s["id"] for s in fx["scenarios"]}
    assert {"office-floor", "electrician", "vegetarian", "blood-type"} <= ids
    assert fx["counting"]["sizes"] == [7, 30, 100] and fx["forget"]["text"].endswith("Kisumu")
    base = {b["key"] for b in fx["base_notes"]}
    for s in fx["scenarios"]:
        taught = {t["key"] for t in s["teach"]} | base
        for q in s["questions"]:
            Spec("x", s["ability"], "s", q["q"], rule=q["rule"])  # a known rule
            for k in [k for g in q.get("needed", []) for k in g] + q.get("stale", []) + q.get("out_of_window", []):
                assert k in taught, (s["id"], k)
        for t in s["teach"]:
            assert t["kind"] in ("note", "chat") and (t["kind"] == "note" or t.get("date"))
    keys = [n["key"] for n in fx["needles"]["items"]]
    assert len(keys) == len(set(keys)) == 25


def test_bench_maps_admitted_notes_back_to_their_facts(tmp_path, monkeypatch):
    """The glue in scripts/engine_bench.py: CAMR Personal's own read path, scored through note checksums."""
    from camr.memory.embedder import HashingEmbedder

    spec_ = importlib.util.spec_from_file_location("engine_bench", Path(__file__).parents[1] / "scripts" / "engine_bench.py")
    eb = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(eb)
    asst = eb.make_assistant(tmp_path / "home", HashingEmbedder(384), min_similarity=0.2)
    assert eb.read_path(asst)["token_budget"] == 384 and eb.read_path(asst)["chunk_tokens"] == 120
    docs = [eb.teach_item(asst, {"key": "floor", "kind": "note", "text": "My office is on the 5th floor of Delta House."}),
            eb.teach_item(asst, {"key": "bike", "kind": "chat", "date": "2026-10-13", "text": "I fixed my bike."})]
    rec = eb.ask(asst, Spec("q", "A1", "t", "Which floor of Delta House is my office on?", needed=[{"floor"}]),
                 eb.note_keys(asst.engine, docs), preview=True)
    assert rec["passed"] and rec["context"][0]["keys"] == ["floor"]
    assert asst.store.conn.execute("SELECT text FROM note WHERE text LIKE 'On 2026-10-13 the user said:%'").fetchone()
    asst.close()


# ---------------------------------------------------------------------- the answer must survive in the context
def test_answer_evidence_is_the_gold_string_or_the_sentence_most_like_it():
    from camr.eval.abilities import Evidence, answer_evidence

    turn = ["I upgraded my internet last week. It is 500 Mbps now and much faster. Thanks for the tips!"]
    assert answer_evidence(turn, "500 Mbps") == Evidence("string", "500 mbps")
    rubric = "The user would prefer suggestions about Adobe Premiere Pro tutorials and editing plugins."
    ev = answer_evidence(["I edit videos daily. I have been using Adobe Premiere Pro for a year."], rubric)
    assert ev.kind == "sentence" and "premiere" in ev.text
    assert answer_evidence(turn, 2) == Evidence("none")  # a bare count: nothing to look for


def test_a_needed_note_counts_only_if_its_answer_survives():
    from camr.eval.abilities import Evidence

    spec = Spec("q", "A1", "s", "What speed is my new internet plan?", needed=[{"t"}],
                evidence=[Evidence("string", "500 mbps")])
    kept = run(spec, [c(["t"], text="- [2023-05-22] The user said: It is 500 Mbps now.")])
    assert kept["passed"] and kept["answered"] == 1
    cut = run(spec, [Cand(frozenset(["t"]), 10, "- I upgraded my internet last week.", 0.7, 1, True, True,
                          compressed=True)])
    assert not cut["passed"] and cut["reached"] == 1 and cut["answered"] == 0 and cut["misses"] == ["answer cut"]
    other = run(spec, [c(["t"], text="- Thanks for the tips!")])
    assert not other["passed"] and other["misses"] == ["answer in another chunk"]
    vague = Spec("q", "A2", "s", "How many?", needed=[{"t"}], evidence=[Evidence("none")])
    assert run(vague, [c(["t"], text="- whole note")])["passed"]
    assert not run(vague, [Cand(frozenset(["t"]), 10, "- part", 0.7, 1, True, True, compressed=True)])["passed"]
