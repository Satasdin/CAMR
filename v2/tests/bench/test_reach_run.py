"""The reach benchmark on fakes: where each set-up keeps the moments and what its questions can reach."""

import sys
from pathlib import Path

import pytest

from engram.bench import reach_run

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # test_core's fakes

pytest.importorskip("mlx")


def contender(setup, other=()):
    from test_core import FakeEmbedder, FakeReader

    return reach_run.Reaches("fake", setup, other=other, reader=FakeReader(), embedder=FakeEmbedder(),
                             room_tokens=60, join=0.99, dates=lambda d: __import__("datetime").date(2025, 9, 21 + d))


def tell_weeks(c, tmp_path):
    c.open(tmp_path / "mem")
    c.tell("User: The oven is a Ramtons.", 1)  # week 1
    c.tell("User: The fryer is a Hotpoint.", 7)  # week 2
    return c


def test_each_week_is_its_own_session_and_the_questions_reach_only_the_last(tmp_path):
    c = tell_weeks(contender("session"), tmp_path)
    assert sorted(c.memories) == ["session:w01", "session:w02"] and c.last_session == "session:w02"
    assert [m.reach for m in c.reads()] == ["session:w02"]
    got = c.ask("Which brand is the oven?", max_tokens=20, family="fact")
    assert got.extra["reach"] == "session:w02" and got.metrics["tier"] in ("ssd", "ram")
    c.close()


def test_project_keeps_every_week_and_global_holds_the_other_project_too(tmp_path):
    c = tell_weeks(contender("project", other=[(1, "User: Their oven is a Mika.")]), tmp_path)
    assert sorted(c.memories) == ["project:longhaul"] and c.memories["project:longhaul"].rooms.moments
    assert c.other == []  # the project set-up is never told the other project
    c.close()
    g = tell_weeks(contender("global", other=[(1, "User: Their oven is a Mika."), (9, "User: Later.")]), tmp_path)
    assert sorted(g.memories) == ["global"] and len(g.memories["global"].rooms.moments) == 3  # day 9 not yet
    g.close()
    pg = tell_weeks(contender("project+global", other=[(1, "User: Their oven is a Mika.")]), tmp_path)
    assert sorted(pg.memories) == ["global", "project:longhaul"]
    assert sorted(m.reach for m in pg.reads()) == ["global", "project:longhaul"]
    before = {m.reach: (dict(m.tiers.used), m.tiers.tick) for m in pg.reads()}
    got = pg.ask("Which brand is the oven?", max_tokens=20, family="fact")
    assert got.extra["reach"] in ("global", "project:longhaul")
    assert {m.reach: (dict(m.tiers.used), m.tiers.tick) for m in pg.reads()} == before  # read-only
    assert pg.describe()["setup"] == "project+global" and pg.name == "engine:fake@project+global"
    pg.close()


def test_an_unknown_setup_is_refused():
    with pytest.raises(ValueError):
        reach_run.Reaches("fake", "everywhere", reader=object(), embedder=object())
