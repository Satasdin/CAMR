"""Reader bench (scripts/reader_bench.py): each question type gets LongMemEval's judging rule, and a model that says
it cannot answer is counted as declining."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("reader_bench",
                                               Path(__file__).resolve().parents[1] / "scripts/reader_bench.py")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)


def row(**kw):
    return {"qid": "q1", "ability": "A1", "type": "single-session-user", "question": "Q?", "answer": "Gold"} | kw


def test_each_question_type_gets_its_judging_rule():
    assert "off-by-one" in rb.judge_prompt(row(type="temporal-reasoning"), "x")
    assert "updated answer" in rb.judge_prompt(row(type="knowledge-update"), "x")
    assert "Rubric:" in rb.judge_prompt(row(type="single-session-preference", ability="A6"), "x")
    assert "unanswerable" in rb.judge_prompt(row(qid="q1_abs"), "x")
    plain = rb.judge_prompt(row(), "x")
    assert "Correct answer: Gold" in plain and "off-by-one" not in plain and "updated answer" not in plain


def test_verdicts_and_declines_are_read():
    assert rb.verdict("Yes.") is True and rb.verdict("no") is False and rb.verdict("maybe") is None
    for text in ("Your cat's name is not mentioned in the notes.", "I'm sorry, but I can't assist with that.",
                 "I don't know that yet. Could you tell me?"):
        assert rb.declined(text), text
    assert not rb.declined("You graduated in Business Administration.") and not rb.declined("")


def test_the_prompt_is_the_apps_own_with_or_without_notes():
    r = row(context="- the user said: I studied law.\n", question_date="2023/05/30")
    assert "I studied law" in rb.prompt_for(r, True) and "I studied law" not in rb.prompt_for(r, False)
    assert rb.NO_NOTES in rb.prompt_for(r, False)
