"""The agent's errands: each quiz question becomes a task whose tool needs that fact, graded like the quiz.
No model is loaded."""

from __future__ import annotations

from engram.agent import FORMS, grade, parse, tasks
from engram.ruler.life import build


def test_every_question_in_every_life_becomes_an_errand():
    for persona in ("student", "farmer", "developer"):
        life = build(persona, 1)
        assert len(tasks(life)) == len(life.questions) == 100


def test_a_tool_call_is_read_from_the_reply():
    text = '<tool_call>\n{"name": "book_ride", "arguments": {"destination": "Nakuru"}}\n</tool_call>'
    assert parse(text) == ("book_ride", {"destination": "Nakuru"})
    assert parse("I can't do that.") == (None, {})


def test_errands_are_graded_like_the_quiz():
    life = build("farmer", 0)
    t = next(t for t in tasks(life) if t.tool == "book_ride" and t.question.kind == "single")
    day = 83
    value = t.question.answer_on(day)[0]
    assert grade(t, "book_ride", {"destination": value}, day) == "right"
    assert grade(t, "order_food", {"dish": value}, day) == "wrong"
    assert grade(t, "ask_user", {"question": "Where?"}, day) == "missed"
    never = next(t for t in tasks(life) if t.question.kind == "abstain")
    assert grade(never, "ask_user", {"question": "?"}, day) == "right_abstain"
    assert grade(never, never.tool, {never.arg: "Nairobi"}, day) == "false_memory"
    assert len(FORMS) == 9


def test_newer_qwen_tool_calls_are_read_too():
    xml = ("<tool_call>\n<function=set_reminder>\n<parameter=person>\nmy neighbour\n</parameter>\n"
           "<parameter=date>\n10 October\n</parameter>\n</function>\n</tool_call>")
    assert parse(xml) == ("set_reminder", {"person": "my neighbour", "date": "10 October"})
