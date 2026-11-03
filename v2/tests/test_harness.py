"""The harness: a run walks the days, quizzes each week, and leaves a test record a chart can be drawn from.
No model is loaded: the contenders here answer from the life itself."""

from __future__ import annotations

import json

from engram.models import Reply
from engram.ruler.chart import _nice, draw
from engram.ruler.contenders import Contender
from engram.ruler.harness import run
from engram.ruler.life import build


class Oracle(Contender):
    """Answers every question right from the notes it has seen: knows rises with what was told."""

    name = "perfect"

    def __init__(self, life):
        self.life, self.seen = life, -1

    def observe(self, day):
        self.seen = day.index

    def answer(self, question):
        q = next(q for q in self.life.questions if q.text == question)
        right = q.answer_on(self.seen)
        return Reply(right[0] if right else "I don't know.", 0.5, 30.0, 100, 5)


class Forgetful(Contender):
    name = "bare"

    def answer(self, question):
        return Reply("I don't know.", 0.2, 40.0, 50, 4)


def test_a_run_records_every_week_and_the_oracle_knows_all_it_was_told(tmp_path):
    life = build("developer", 0)
    path = run(life, Oracle(life), weeks=3, records=tmp_path / "records", progress=lambda m: None)
    rec = json.loads(path.read_text())
    assert [w["week"] for w in rec["weeks"]] == [1, 2, 3]
    for w in rec["weeks"]:
        s = w["summary"]
        assert s["knows"] == s["told"] and s["honest"] == s["untold"] and s["false_memories"] == 0
        assert len(w["answers"]) == 100 and s["wait_median_s"] == 0.5
    assert rec["environment"]["python"] and rec["contender"]["name"] == "perfect"


def test_the_chart_draws_both_contenders_from_their_records(tmp_path):
    life = build("developer", 0)
    records = tmp_path / "records"
    run(life, Oracle(life), weeks=2, records=records, progress=lambda m: None)
    run(life, Forgetful(), weeks=2, records=records, progress=lambda m: None)
    svg = draw("developer", 0, records).read_text()
    assert svg.startswith("<svg") and "perfect reader" in svg and "1.7B alone" in svg and "told so far" in svg


def test_axis_tops_are_round_so_gridlines_land_on_round_numbers():
    assert [_nice(t) for t in (22.1, 17.3, 3.35, 1.0)] == [24, 20, 4, 1]
    assert _nice(0.2) == 0.2
