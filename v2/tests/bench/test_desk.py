"""The engine's desk with several rooms, conventional RAG on the Long Haul, and reading one saved memory several ways
(camr_engine.bench.desk)."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from camr_engine.bench import desk as dk
from camr_engine.bench import local
from camr_engine.bench.contender import METRICS, run

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("mlx")
from test_core import FakeEmbedder, FakeReader, desk_values, make, numbers  # noqa: E402

FACTS = ["the oven brand is Ramtons.", "the oven was serviced by Otieno.", "the van plate is KDA 123X.",
         "the fridge is a Haier."]


def dates(day: int) -> dt.date:
    return dt.date(2025, 9, 21) + dt.timedelta(days=day)


def rooms_apart(path, **kw):
    """A memory where every moment is a room of its own."""
    m = make(path, room_tokens=60, join=0.99, **kw)
    for day, f in enumerate(FACTS):
        m.remember(f, day)
    return m


# -- the engine's desk


def test_one_room_on_the_desk_is_as_before(tmp_path):
    m = rooms_apart(tmp_path / "m")
    rec = m.recall("Which brand is the oven?")
    assert rec.laid == [rec.room] and rec.more == [] and rec.notes == rec.tokens
    assert rec.desk[0].offset == m.notebook.p + rec.tokens and rec.in_view == rec.tokens + rec.words


def test_further_rooms_go_on_the_desk_oldest_first_each_slid_to_its_place(tmp_path):
    import mlx.core as mx

    from camr_engine.notes import turn

    m = rooms_apart(tmp_path / "m", desk_rooms=2)
    rec = m.recall("Who serviced the oven brand?")
    assert len(rec.laid) == 2 and set(rec.laid) == {0, 1} and rec.laid == [0, 1]  # in the order they were told
    a, b = (len(FACTS[0]) + 1, len(FACTS[1]) + 1)
    p = m.notebook.p
    assert rec.notes == a + b and rec.desk[0].offset == p + a + b
    assert desk_values(rec.desk)[p:].tolist() == numbers(FACTS[0]) + numbers(FACTS[1])
    raw = m._array(m.rooms.fetch([1])[1], 1).transpose(1, 2, 3, 0, 4)
    want = turn(raw[0, 0], mx.full((b,), a, dtype=mx.int32), m.notebook.shape.rope_base)
    got = rec.desk[0].keys[0, :, p + a:p + a + b, :]
    assert np.allclose(np.array(got.astype(mx.float32)), np.array(want.astype(mx.float32)), atol=1e-3)
    m.answer("Who serviced the oven brand?", dt.date(2026, 1, 20))
    call = m.reader.calls[-1]
    assert call.offset == p + a + b  # the words come after both rooms


def test_the_best_room_can_go_last_nearest_the_question(tmp_path):
    m = rooms_apart(tmp_path / "m", desk_rooms=3, desk_order="best_last")
    rec = m.recall("Which brand is the oven?")
    assert rec.laid[-1] == rec.room and len(rec.laid) == 3


def test_further_rooms_are_awake_ones_within_the_token_budget(tmp_path):
    from camr_engine.swap import Tiers

    m = rooms_apart(tmp_path / "m", desk_rooms=4, desk_tokens=len(FACTS[0]) + len(FACTS[1]) + 2,
                    tiers=Tiers(ram_bytes=10**9))
    rec = m.recall("Who serviced the oven brand? the van?")
    assert rec.notes <= len(FACTS[0]) + len(FACTS[1]) + 2 and len(rec.laid) == 2
    m.tiers.sleep(1)
    rec = m.recall("Who serviced the oven brand?")
    assert 1 not in rec.more  # an asleep room would be read as words: not laid as a further room


def test_a_desk_needs_a_room_and_a_known_order(tmp_path):
    with pytest.raises(ValueError):
        make(tmp_path / "a", desk_rooms=0)
    with pytest.raises(ValueError):
        make(tmp_path / "b", desk_order="random")


# -- RAG on the Long Haul


def rag(**kw):
    return local.Rag("fake", reader=FakeReader(), embedder=FakeEmbedder(), dates=dates, intro=local.LONGHAUL_INTRO,
                     **kw)


def test_rag_pastes_the_closest_moments_as_text_within_its_budget(tmp_path):
    r = rag(k=2, budget=200)
    r.open(tmp_path / "rag")
    for day, f in enumerate(["User: " + x for x in FACTS], start=1):
        r.tell(f, day)
    r.tell("Day 9 · Tuesday 30 September 2025", 9)  # carried by every moment instead
    assert r.moments == 4 and r.texts[0] == "[2025-09-22, day 1] User: the oven brand is Ramtons."
    a = r.ask("Who serviced the oven?", max_tokens=120, family="fact")
    call = r.reader.calls[-1]
    head, rest = r.prompt(dates(9), "Who serviced the oven?", local.hint("fact"))  # the day line moved today on
    picked = [0, 1]  # the two closest, in date order
    assert call.offset == r.notebook.p == len(head)  # only the header is already read
    assert call.ids == [i for m in picked for i in r.ids(r.texts[m])] + rest
    assert set(a.metrics) == set(METRICS) and a.metrics["tier"] == "vault" and a.metrics["bytes_read"] == 0
    assert a.extra["memory_notes"] == 0 and a.extra["memory_words"] == a.extra["memory_in_view"] > 0
    assert a.extra["prefill_tokens"] == len(call.ids) and a.extra["moments_read"] == 2
    assert a.metrics["context_tokens"] == len(head) + len(call.ids) and a.metrics["disk_gb"] > 0
    assert (tmp_path / "rag" / "vectors.npy").exists() and json.loads((tmp_path / "rag" / "index.json")
                                                                      .read_text())["moments"] == r.texts
    small = rag(k=8, budget=len(r.ids(r.texts[3])))
    small.open(tmp_path / "small")
    for day, f in enumerate(["User: " + x for x in FACTS], start=1):
        small.tell(f, day)
    assert small.pick("Which fridge?")[0] == [3]  # one moment fits the budget; longer ones are passed over
    d = r.describe()
    assert d["k"] == 2 and d["budget_tokens"] == 200 and d["order"] == "date" and d["system"] == local.LONGHAUL_INTRO
    assert r.status()["moments"] == 4 and "peak_footprint_gb" in r.status()
    r.close()


def test_rag_can_keep_the_closest_first():
    r = rag(k=3, order="score")
    r.open(Path(__import__("tempfile").mkdtemp()))
    for day, f in enumerate(FACTS, start=1):
        r.tell(f, day)
    r.ask("x", max_tokens=8)  # saves the vectors
    picked, scores = r.pick("the van plate?")
    assert picked[0] == 2 and scores == sorted(scores, reverse=True)
    with pytest.raises(ValueError):
        rag(order="random")


def test_the_long_hauls_contenders_carry_their_settings_in_their_names():
    loader = local.Loader()
    c = local.haul_contender("rag:qwen3-4b", loader, rag=local.parse_settings("rag", "k=16,budget=2048"))
    assert c.name == "rag:qwen3-4b[budget=2048,k=16]" and c.k == 16 and c.budget == 2048
    assert c.intro == local.LONGHAUL_INTRO
    e = local.haul_contender("engine:qwen3-4b", loader, desk=local.parse_settings("engine", "rooms=3,order=date"))
    assert e.name == "engine:qwen3-4b[order=date,rooms=3]" and e.settings["desk_rooms"] == 3
    assert local.haul_contender("rag:qwen3-4b", loader).name == "rag:qwen3-4b"
    with pytest.raises(ValueError):
        local.parse_settings("rag", "rooms=2")
    assert local.parse("rag:qwen3-4b") == ("rag", "qwen3-4b")
    a = local.parser().parse_args(["longhaul", "--contender", "rag:qwen3-4b", "--rag", "k=8", "--snapshots", "/tmp/s"])
    assert a.rag == "k=8" and a.snapshots == Path("/tmp/s")


# -- one memory, read several ways


def engine(**kw):
    return local.Engine("fake", reader=FakeReader(), embedder=FakeEmbedder(), log=False, room_tokens=60, join=0.99,
                        dates=dates, intro=local.LONGHAUL_INTRO, **kw)


def test_a_run_keeps_a_clone_of_the_memory_at_each_cut_and_it_reads_back_several_ways(tmp_path):
    e = engine(snapshots=tmp_path / "snaps")
    events = [{"day": d, "role": "user", "text": f, "tokens": 6} for d, f in enumerate(FACTS, start=1)]
    cps = [{"name": "64K", "tokens": 12, "events": 2, "questions": [{"id": "q", "question": "Which oven?",
                                                                     "family": "fact"}]},
           {"name": "256K", "tokens": 24, "events": 4, "questions": [{"id": "q", "question": "Which oven?",
                                                                      "family": "fact"}]}]
    run(e, events, cps, task="longhaul", folder=tmp_path / "mem", records=tmp_path / "rec", grader=None,
        progress=lambda m: None)
    snap = tmp_path / "snaps" / "64K.nosync"
    told = json.loads((snap / "snapshot.json").read_text())
    assert told["events"] == 2 and told["day"] == 2 and told["moments"] == 2
    again = engine()
    again.attach(snap, told["day"])
    assert again.moments == 2 and again.days.now() == dates(2)
    a = again.ask("Which brand is the oven?", max_tokens=120, family="fact")
    assert a.extra["rooms_laid"] == 1 and a.extra["memory_in_view"] == a.extra["memory_notes"] + a.extra["memory_words"]
    dk.configure(again, {"desk_rooms": 2})
    b = again.ask("Which brand is the oven?", max_tokens=120, family="fact")
    assert b.extra["rooms_laid"] == 2 and b.extra["memory_notes"] > a.extra["memory_notes"]
    dk.configure(again, {})
    assert again.memory.desk_rooms == 1 and again.memory.closest == 4
    r = dk.rag_over(again, k=1)
    got = r.ask("Which brand is the oven?", max_tokens=120, family="fact")
    assert got.extra["moments_read"] == 1 and got.metrics["disk_gb"] is None and r.texts == [
        m.text for m in again.memory.rooms.moments]
    again.close()
    assert (tmp_path / "snaps" / "256K.nosync" / "project" / "longhaul" / "index.json").exists()
    with pytest.raises(FileNotFoundError):
        engine().attach(tmp_path / "nothing", 1)


def test_variants_are_named_and_checked():
    assert dk.parse_variant("camr") == ("camr", {})
    assert dk.parse_variant("camr:rooms=3,tokens=2048") == ("camr", {"desk_rooms": 3, "desk_tokens": 2048})
    assert dk.parse_variant("rag:k=8,budget=1024,order=score") == ("rag", {"k": 8, "budget": 1024, "order": "score"})
    assert dk.variant_name("qwen3-4b", "camr", {"desk_rooms": 3}) == "engine:qwen3-4b[rooms=3]"
    assert dk.variant_name("qwen3-4b", "rag", {}) == "rag:qwen3-4b"
    with pytest.raises(ValueError):
        dk.parse_variant("bm25:k=3")
    with pytest.raises(ValueError):
        dk.parse_variant("camr:k=3")


def test_moments_already_on_the_desk_need_not_be_read_again_as_words(tmp_path):
    m = rooms_apart(tmp_path / "m", desk_rooms=2, reread="off_desk")
    m.answer("Who serviced the oven brand?", dt.date(2026, 1, 20))
    call = m.reader.calls[-1]
    words = "".join(chr(i - 1) for i in call.ids)
    assert "Ramtons" not in words and "Otieno" not in words  # both are in the two rooms laid as notes
    assert "KDA 123X" in words  # a closest moment from a room not on the desk is still read as words
    with pytest.raises(ValueError):
        make(tmp_path / "x", reread="some")
