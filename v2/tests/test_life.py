"""The scripted lives: fixed by persona and seed, 100 questions of the planned kinds, and every right answer really
told in that day's notes."""

from __future__ import annotations

from collections import Counter

import pytest

from engram.ruler.grade import names, norm
from engram.ruler.life import COUNTS, DAYS, PERSONAS, build


@pytest.mark.parametrize("persona", sorted(PERSONAS))
def test_a_life_is_the_same_every_time_and_differs_by_seed(persona):
    a, b, c = build(persona, 1), build(persona, 1), build(persona, 2)
    assert [d.notes for d in a.days] == [d.notes for d in b.days]
    assert [q.text for q in a.questions] == [q.text for q in b.questions]
    assert [d.notes for d in a.days] != [d.notes for d in c.days]


@pytest.mark.parametrize("persona", sorted(PERSONAS))
def test_the_quiz_has_the_planned_kinds_and_weekly_days(persona):
    life = build(persona, 1)
    assert len(life.days) == DAYS and len(life.questions) == 100
    assert Counter(q.kind for q in life.questions) == Counter(COUNTS)
    assert len({q.text for q in life.questions}) == 100
    assert life.quiz_days == [6 + 7 * w for w in range(12)]
    assert sum(not d.notes for d in life.days) >= 4  # a gap of several days, plus quiet days


@pytest.mark.parametrize("persona", sorted(PERSONAS))
def test_every_right_answer_is_told_in_that_days_notes(persona):
    life = build(persona, 1)
    for q in life.questions:
        if q.kind == "abstain":
            assert q.timeline == () and q.answer_on(DAYS) is None
            continue
        for day, value, aliases in q.timeline:
            if q.kind == "time":
                continue  # the date is in the note's stamp ("today", or the day before for "yesterday")
            # a two-note fact is answerable once both are told; its value may come in the earlier note
            told = life.days[day:day + 1] if q.kind != "multi" else life.days[:day + 1]
            assert names(" ".join(n for d in told for n in d.notes), aliases), (q.text, day, value)
    for q in (q for q in life.questions if q.kind == "update"):
        (d1, v1, _), (d2, v2, _) = q.timeline
        assert d2 >= d1 + 7 and v1 != v2
        assert q.answer_on(d1 - 1) is None and q.answer_on(d1)[0] == v1 and q.answer_on(d2)[0] == v2
        assert q.superseded_on(d2) and not q.superseded_on(d1)


def test_time_answers_are_the_day_of_the_note_or_the_day_before():
    life = build("student", 1)
    for q in (q for q in life.questions if q.kind == "time"):
        (day, value, aliases), = q.timeline
        note = next(n for n in life.days[day].notes if q.text.split(" I ", 1)[1].rstrip("?") in n)
        date = life.days[day - 1 if "esterday" in note else day].date
        assert date.isoformat() in aliases


def test_knowledge_grows_through_the_twelve_weeks():
    life = build("farmer", 1)
    told = [life.told_on(d) for d in life.quiz_days]
    assert told == sorted(told) and told[0] >= 3 and told[-1] == 100 - COUNTS["abstain"]


def test_names_do_not_match_inside_other_words():
    assert norm("The 14th of February, 2026!") == " the 14 february 2026 "
    assert not names("She lives in Kisumu Ndogo-ish", ("su",))
