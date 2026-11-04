"""Memory that revises itself: a moment close to one already kept is judged SAME (not kept again), UPDATE (kept,
the old note tagged superseded and linked) or NEW; a moment far from every other is kept with no judge."""
from __future__ import annotations

import pytest

pytest.importorskip("mlx")

from test_core import FakeEmbedder, FakeReader  # noqa: E402

from camr_engine.memory import Memory  # noqa: E402
from camr_engine.models import Reply  # noqa: E402
from camr_engine.revise import mark, revise  # noqa: E402


class Judge(FakeReader):
    word = "UPDATE"
    asked = 0

    def generate(self, ids, cache=None, max_tokens=None):
        if max_tokens == 3:
            self.asked += 1
            return Reply(self.word, 0.001, 100.0, len(ids), 1, [self.word])
        return super().generate(ids, cache, max_tokens)


def test_a_close_moment_is_judged_and_a_far_one_is_not(tmp_path):
    r = Judge()
    m = Memory(r, FakeEmbedder(), tmp_path / "m", vault=True, log=False, room_tokens=400, join=0.2)
    m.remember("Iten Traders minimum order is KES 48500.", 1)
    rv = revise(m, r, m.embedder, "Iten Traders minimum order is KES 52000.")
    assert rv["verdict"] == "update" and rv["old"] == 0 and "updates an earlier note" in rv["text"]
    new = m.remember(rv["text"], 2)
    mark(m, rv["old"], new.mid)
    assert "superseded" in m.vault.get(m.vault.moment_id(0)).tags
    r.word = "SAME"
    assert revise(m, r, m.embedder, "Iten Traders minimum order is KES 48500.")["text"] is None
    asked = r.asked
    far = revise(m, r, m.embedder, "Birthday cake for my sister in March.")
    assert far["verdict"] == "new" and r.asked == asked  # far from everything: no judge


def test_a_web_moment_is_never_compared_with_what_the_user_said(tmp_path):
    from camr_engine.revise import source

    r = Judge()
    m = Memory(r, FakeEmbedder(), tmp_path / "m", vault=True, log=False, room_tokens=400, join=0.2)
    m.remember("Iten Traders minimum order is KES 48500.", 1)
    web = "[2026-11-05] From the web (Iten, https://x), not something the user said. Iten Traders minimum order is KES 1."
    assert source(web) == "web" and source("Iten Traders minimum order is KES 48500.") == "user"
    assert revise(m, r, m.embedder, web)["verdict"] == "new" and r.asked == 0
