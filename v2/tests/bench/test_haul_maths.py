"""The maths course: every answer is computed twice (the taught method and brute force) and they agree, the doc's
samples come out as written, and no trap equals the right answer."""

from __future__ import annotations

import random
from fractions import Fraction

import pytest
from haul_shared import built

from camr_engine.bench.haul import grade, maths
from camr_engine.bench.haul.maths import FAMILIES, fmt, problems


def _params(p: dict) -> dict:
    out = dict(p)
    if "percent" in out:
        out["percent"] = Fraction(out["percent"])
    return out


@pytest.mark.parametrize("seed", range(6))
def test_every_computed_answer_matches_brute_force(seed):
    probs = problems(random.Random(f"{seed}:maths"), 110)
    assert len(probs) == 40 and len({p.pid for p in probs}) == 40
    assert {p.family for p in probs} == set(FAMILIES)
    for prob in probs:
        fam = FAMILIES[prob.family]
        assert [a.way for a in prob.asks] == ["same", "new", "rule"]
        for a in prob.asks:
            assert fam.solve(a.params) == fam.brute(a.params) == a.answer, (prob.pid, a.way, a.params)
            assert a.answer not in a.trap
        assert fmt(prob.asks[0].answer) in prob.correction  # the correction shows the right answer
        assert prob.asks[0].text == prob.ask


def test_the_built_probes_answers_are_correct():
    for p in [p for p in built().probes if p["family"] == "maths"]:
        fam = FAMILIES[p["method"]]
        params = _params(p["params"])
        assert str(fam.solve(params)) == str(fam.brute(params)) == p["answer"], p["id"]
        assert p["grader"]["value"] == p["answer"]


def test_the_rule_ask_needs_the_house_rule():
    for prob in problems(random.Random("1:maths"), 110):
        rule = prob.asks[2]
        if prob.family == "fee":
            continue  # the fee is itself the invented rule; its rule case triggers the flat fee or the minimum
        plain = FAMILIES[prob.family].solve(dict(rule.params, rule=None))
        assert plain != rule.answer and plain in rule.trap, prob.pid


def test_the_doc_samples():
    fee = maths.Fee()
    base = dict(percent=Fraction(1), step=5, minimum=10, multiple=1000, flat=25)
    assert [fee.solve(dict(base, amount=a)) for a in (3456, 12000, 7321)] == [35, 25, 75]
    sq = maths.Squares()
    assert sq.solve(dict(a=1, p=5, N=10000)) == sq.brute(dict(a=1, p=5, N=10000)) == 4000
    assert sq.solve(dict(a=1, p=13, N=25000)) == sq.brute(dict(a=1, p=13, N=25000)) == 3846
    assert sq.roots(1, 13) == [5, 8] and 25000 // 13 == 1923


def test_samples_keep_their_days_and_words():
    probs = {p.pid: p for p in problems(random.Random("1:maths"), 110)}
    assert probs["maths-01"].day == 3 and probs["maths-02"].day == 9
    assert probs["maths-01"].ask == "What's our fee on a KES 3,456 payment?"
    assert probs["maths-02"].ask == "How many n from 1 to 10,000 make n² + 1 divisible by 5?"
    assert [a.text for a in probs["maths-01"].asks[1:]] == ["Fee on 7,321?", "Fee on 12,000?"]
    assert probs["maths-01"].ask_days == {"new": 97, "rule": 97}
    assert probs["maths-02"].ask_days == {"new": 102}


def test_the_scripted_first_answer_is_wrong():
    for prob in problems(random.Random("1:maths"), 110):
        same = {"id": prob.pid, "family": "maths", "grader": {"type": "number", "value": str(prob.asks[0].answer)}}
        assert grade(same, prob.reply).verdict != "right", (prob.pid, prob.reply)


def test_course_notes_teach_the_plain_method_only():
    rng = random.Random(0)
    for name in [n for n in FAMILIES if n != "fee"]:
        q, steps = maths.lesson_example(rng, name)
        assert q and "Step 1" in steps
    with pytest.raises(ValueError):
        maths.lesson_example(rng, "fee")
