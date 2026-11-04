"""Grading: the same answer always gets the same verdict, and each verdict means what the record says it means."""

from __future__ import annotations

import pytest

from camr_engine.ruler.grade import abstains, grade
from camr_engine.ruler.life import Question, date_aliases

import datetime as dt

MOVED = Question("q1", "update", "Where does my sister live?",
                 ((3, "Kisumu", ("kisumu",)), (20, "Nakuru", ("nakuru",))))
NEVER = Question("q2", "abstain", "What car does my uncle drive?", ())
WHEN = Question("q3", "time", "What date was it when I paid the semester fees?",
                ((10, "14 February", date_aliases(dt.date(2026, 2, 14))),))


@pytest.mark.parametrize("answer,day,verdict", [
    ("Your sister lives in Kisumu.", 10, "right"),
    ("She moved from Kisumu to Nakuru.", 25, "right"),
    ("Your sister lives in Kisumu.", 25, "stale"),
    ("I don't know.", 25, "missed"),
    ("She lives in Eldoret.", 25, "wrong"),
    ("I don't know.", 1, "right_abstain"),
    ("Your sister lives in Kisumu.", 1, "false_memory"),
])
def test_an_update_question_over_time(answer, day, verdict):
    assert grade(MOVED, answer, day) == verdict


@pytest.mark.parametrize("answer", ["You paid them on 14 February 2026.", "On February 14th.", "2026-02-14",
                                    "the 14th of Feb", "14/02/2026"])
def test_a_date_in_any_usual_form(answer):
    assert grade(WHEN, answer, 30) == "right"


def test_a_near_date_is_wrong():
    assert grade(WHEN, "On 4 February.", 30) == "wrong"


@pytest.mark.parametrize("answer", ["I don't know.", "I do not know", "The notes don't say.", "That isn’t mentioned.",
                                    "There is no information about your uncle's car."])
def test_ways_of_declining(answer):
    assert abstains(answer) and grade(NEVER, answer, 80) == "right_abstain"


def test_a_guess_about_something_never_told_is_a_false_memory():
    assert grade(NEVER, "Your uncle drives a Toyota Probox.", 80) == "false_memory"
