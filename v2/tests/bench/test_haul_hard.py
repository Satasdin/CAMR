"""The Long Haul's hard set: planted into a seed-3 base at depth without moving the base's own probes, every question
backed by events that hold its answer, graders that take the right value and refuse the stale or conflicting one,
templates that share no 4-word phrase with probes.py, and the same build for the same seed."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pytest
from haul_shared import built, need_tokenizer

from camr_engine.bench.haul.grade import grade as base_grade
from camr_engine.bench.haul.grade import names as named
from camr_engine.bench.haul import hard, tokens
from camr_engine.bench.haul.sample import at_cut, sample

BASE_SEED = 3  # the hard set is never planted into seed 1 (the locked exam)


@lru_cache(maxsize=None)
def _hard(seed: int):
    base = built(BASE_SEED)
    return base, hard.harden(base.events, base.probes, base.manifest, seed)


def hard_set(seed: int = 4):
    need_tokenizer()
    return _hard(seed)


def _sha(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


# -- the script ----------------------------------------------------------------------------------------------------

def test_cum_tokens_stay_numbered_monotone_and_counted():
    base, h = hard_set()
    prev = 0
    for k, e in enumerate(h.events):
        assert e["i"] == k
        assert e["tokens"] > 0
        assert e["cum_tokens"] == prev + e["tokens"]
        prev = e["cum_tokens"]
    count = tokens.counter()
    planted = {p.text for p in h.plants}
    new = [e for e in h.events if e["text"] in planted]
    assert len(new) == len(h.plants)
    assert all(count(e["text"]) == e["tokens"] for e in new)
    # noise was taken out to make room, so the length and the 2M cut hardly move
    assert abs(h.events[-1]["cum_tokens"] - base.events[-1]["cum_tokens"]) < 2_000
    assert h.events[-1]["cum_tokens"] >= hard.CUTS["2M"]


def test_base_events_keep_their_order_and_only_noise_is_taken_out():
    base, h = hard_set()
    planted = {p.text for p in h.plants}
    kept = [e for e in h.events if e["text"] not in planted]
    texts = [e["text"] for e in base.events]
    j = 0
    removed = []
    for e in kept:
        while texts[j] != e["text"]:
            removed.append(base.events[j])
            j += 1
        j += 1
    removed += base.events[j:]
    assert len(removed) == h.removed
    assert {e["kind"] for e in removed} <= {"doc", "meeting", "decision", "log"}
    referenced = {base.events[i]["text"] for p in base.probes for i in hard._probe_events(p)}
    assert not referenced & {e["text"] for e in removed}


def test_base_probes_are_reindexed_to_the_same_events_and_answers():
    base, h = hard_set()
    assert len(h.base_probes) == len(base.probes)
    for old, new in zip(base.probes, h.base_probes):
        assert old["id"] == new["id"]
        assert [base.events[i]["text"] for i in old["events"]] == [h.events[i]["text"] for i in new["events"]]
        if old["event"] is not None:
            assert base.events[old["event"]]["text"] == h.events[new["event"]]["text"]
            assert new["planted_at"] == h.events[new["event"]]["cum_tokens"]
        assert (old["ready_at"] is None) == (new["ready_at"] is None)
        if new["ready_at"] is not None:
            assert new["ready_at"] <= hard.CUTS["2M"]
            assert abs(new["ready_at"] - old["ready_at"]) < 5_000
        q = at_cut(new, hard.CUTS["2M"])
        assert q is not None and q["answer"] == at_cut(old, hard.CUTS["2M"])["answer"]


# -- the questions -------------------------------------------------------------------------------------------------

def test_families_and_counts():
    _, h = hard_set()
    assert Counter(p["family"] for p in h.probes) == Counter(hard.FAMILIES)
    assert sum(hard.FAMILIES.values()) == 100
    assert len({p["id"] for p in h.probes}) == 100
    assert all(p["grader"]["type"] in ("exact", "never") for p in h.probes)
    assert h.manifest["hard"] is True and h.manifest["families"] == hard.FAMILIES


def test_every_hard_probe_is_backed_by_events_that_hold_its_answer():
    _, h = hard_set()
    for p in h.probes:
        assert all(0 <= i < len(h.events) for i in p["events"])
        if p["family"] == "negated":
            assert p["events"] == [] and p["ready_at"] is None
            continue
        assert p["event"] in p["events"]
        assert p["planted_at"] == h.events[p["event"]]["cum_tokens"]
        assert p["ready_at"] >= max(h.events[i]["cum_tokens"] for i in p["events"]) or p["family"] == "before_change"
        assert p["ready_at"] <= hard.CUTS["2M"]
        for v in p["evidence"]:
            assert v["event"] in p["events"]
            assert v["text"].casefold() in h.events[v["event"]]["text"].casefold()
        if p["family"] in ("count_changes",) or p.get("op") in ("count", "sum", "diff"):
            continue  # a derived answer: its parts are the evidence above
        assert p["answer"].casefold() in h.events[p["event"]]["text"].casefold(), p["id"]


def test_the_links_of_a_three_hop_are_told_apart_in_different_genres():
    _, h = hard_set()
    by_text = {p.text: p for p in h.plants}
    for p in (q for q in h.probes if q["family"] == "three_hop"):
        links = [by_text[h.events[i]["text"]] for i in p["events"]]
        assert len(links) == 3
        assert len({x.genre for x in links}) == 3
        assert len({x.day for x in links}) == 3
        assert p["grader"]["reject"], "a decoy chain's end value is rejected"


def test_count_changes_count_changes_not_restatements():
    _, h = hard_set()
    for p in (q for q in h.probes if q["family"] == "count_changes"):
        assert len(p["values"]) == p["changes"] + 1
        assert len(set(p["values"])) == len(p["values"])
        assert p["answer"] == str(p["changes"])
        assert p["refused"] not in p["values"]
    traps = sum(len(p["events"]) > len(p["values"]) for p in h.probes if p["family"] == "count_changes")
    assert traps >= 8  # most also have a restatement or a turned-down proposal that is not a change
    counts = Counter(p["changes"] for p in h.probes if p["family"] == "count_changes")
    assert len(counts) >= 4  # 1 to 5 changes, not one count for all


def test_never_said_questions_are_never_told():
    base, h = hard_set()
    for p in (q for q in h.probes if q["family"] == "negated"):
        about = [a.casefold() for a in p["absent"]["about"]]
        values = p["absent"]["values"]
        for e in h.events:
            low = e["text"].casefold()
            if all(a in low for a in about):
                assert values is not None and not named(e["text"], values), (p["id"], e["i"])
        for a in about:  # a near miss: what it is about is in the history, only the asked part never is
            assert any(a in e["text"].casefold() for e in h.events), (p["id"], a)


def test_reworded_questions_share_almost_no_words_with_how_they_were_told():
    _, h = hard_set()
    stop = set("a an the is are was were be to of in on at for by with and or what which who whom where how does do "
               "did their they them it its this that s won t not every from up off can when".split())
    for p in (q for q in h.probes if q["family"] == "reworded"):
        told = h.events[p["event"]]["text"]
        statement = next(x for x in told.split("\n") if p["answer"] in x)
        names = set(re.findall(r"[a-z]+", " ".join(re.findall(r"\b[A-Z][a-z]+\b", p["ask"])).lower()))
        ask = set(re.findall(r"[a-z]+", p["ask"].lower())) - stop - names
        said = set(re.findall(r"[a-z]+", statement.lower())) - stop - names
        assert len(ask & said) <= 1, (p["ask"], statement, ask & said)


# -- grading -------------------------------------------------------------------------------------------------------

def _verdict(p: dict, answer: str) -> str:
    v = hard.grade(p, answer).verdict
    assert v == base_grade(p, answer).verdict  # the wrapper and grade.py agree, so longhaul grades the same
    return v


def test_graders_take_the_right_value_and_refuse_stale_or_conflicting_ones():
    _, h = hard_set()
    seen = Counter()
    for p in h.probes:
        g = p["grader"]
        fam = p["family"]
        if fam == "negated":
            assert _verdict(p, "I don't know; that was never mentioned.") == "right"
            pool = [v for v in g["pool"] if v != "#number"]
            guess = pool[0] if pool else "450"
            assert _verdict(p, f"It is {guess}.") == "false_memory"
            seen[fam] += 1
            continue
        assert _verdict(p, f"{p['answer']}.") == "right", p["id"]
        assert _verdict(p, "I don't know.") == "declined"
        for s in g.get("stale", []):
            assert _verdict(p, f"It was {s}.") == "stale", (p["id"], s)
        for r in g.get("reject", []):
            assert _verdict(p, f"{r}.") == "wrong", (p["id"], r)
            assert _verdict(p, f"{p['answer']}, or maybe {r}.") == "wrong", (p["id"], r)
        if fam == "count_changes":
            n = p["changes"]
            assert _verdict(p, f"It changed {n + 1} times.") == "wrong"
            assert _verdict(p, f"It was changed {['', 'once', 'twice', 'three times', 'four times', 'five times'][n]}"
                               f".") == "right"
        seen[fam] += 1
    assert set(seen) == set(hard.FAMILIES)


def test_conflict_rumour_is_stale_and_correction_wins():
    _, h = hard_set()
    shapes = Counter()
    for p in (q for q in h.probes if q["family"] == "conflict"):
        shapes[p["shape"]] += 1
        rumour = p["rumour"].removeprefix("KES ").removeprefix("the ")
        assert _verdict(p, f"{rumour}") == "stale"
        assert _verdict(p, f"The memo confirmed {p['answer']}.") == "right"
    assert set(shapes) == {"rumour_then_memo", "memo_then_rumour", "correction"}


def test_far_lookalikes_reject_the_other_ones_value_and_are_told_months_apart():
    _, h = hard_set()
    for p in (q for q in h.probes if q["family"] == "far_lookalike"):
        a, b = (h.events[i] for i in p["events"])
        assert abs(a["day"] - b["day"]) >= 40
        assert _verdict(p, p["grader"]["reject"][0]) == "wrong"


def test_aggregates_combine_several_facts():
    _, h = hard_set()
    for p in (q for q in h.probes if q["family"] == "aggregate"):
        assert len(p["events"]) >= 5
        prices = p["prices"]
        if p["op"] == "max":
            assert p["answer"] == max(prices, key=prices.get)
            other = min(prices, key=prices.get)
            assert _verdict(p, f"{p['answer']} or {other}") == "wrong"
        elif p["op"] == "count":
            assert int(p["answer"]) == sum(1 for v in prices.values() if v > p["threshold"])


# -- templates -----------------------------------------------------------------------------------------------------

def test_templates_share_no_four_word_phrase_with_the_existing_families():
    strings = hard.probes_py_strings()
    assert len(strings) > 100
    t = hard.templates()
    assert hard.phrase_clashes(t["ask"], strings) == []
    assert hard.phrase_clashes(t["say"], strings) == []
    # the check would catch a copied template
    assert hard.phrase_clashes(["Which branch does {e} work at?"], strings)


def test_asked_questions_share_no_five_word_phrase_with_the_base_questions():
    base, h = hard_set()
    assert hard.phrase_clashes([p["ask"] for p in h.probes], [p["ask"] for p in base.probes], n=5) == []


# -- determinism, disk and the runners -----------------------------------------------------------------------------

def test_the_build_is_the_same_for_a_seed_and_different_for_another():
    need_tokenizer()
    base, h = hard_set(4)
    again = hard.harden(base.events, base.probes, base.manifest, 4)
    assert _sha(again.events) == _sha(h.events)
    assert _sha(again.probes) == _sha(h.probes)
    assert _sha(again.base_probes) == _sha(h.base_probes)
    _, other = hard_set(5)
    assert [p["ask"] for p in other.probes] != [p["ask"] for p in h.probes]


def test_written_dir_drives_longhaul_and_sample_with_hard_questions_only(tmp_path: Path):
    from camr_engine.bench.longhaul import checkpoints, grader

    _, h = hard_set()
    out = tmp_path / "s4-hard"
    hard.write(h, out)
    assert json.loads((out / "manifest.json").read_text())["hard"] is True
    events, cps = checkpoints(out, {"1M": 1_000_000, "2M": 2_000_000})
    assert len(events) == len(h.events)
    last = cps[-1]
    fams = Counter(q["family"] for q in last["questions"])
    assert set(fams) == set(hard.FAMILIES)
    assert all(n == min(10, hard.FAMILIES[f]) for f, n in fams.items())
    q = last["questions"][0]
    assert grader(q, q["expected"])["right"] or q["family"] == "negated"
    picked = sample(hard.load_base(out), hard.CUTS["2M"], 2, per_family=True)
    assert {"fact", "changed", "maths"} <= {p["family"] for p in picked}


def test_never_built_from_the_locked_exam(tmp_path: Path):
    with pytest.raises(SystemExit):
        hard.build(tmp_path / "s1", 4)
    with pytest.raises(SystemExit):
        hard.build(tmp_path / "s1-16m", 4)
