"""How hard each written word looks at the desk: only a written word's step is looked at, and its numbers are worked
out at once, so a long answer on a long desk does not hold every layer's keys until the GPU runs out."""

from __future__ import annotations

from collections import defaultdict

import pytest

mx = pytest.importorskip("mlx.core")

from camr_engine.events import Looks  # noqa: E402


def looks(prompt_len: int) -> Looks:
    lk = object.__new__(Looks)
    lk.nodes, lk.lo, lk.hi = [7, 9], 1, 4
    lk.a = mx.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    lk.prompt_len, lk.calls = prompt_len, defaultdict(dict)
    lk.layer_of = {id("cache"): 12}
    lk._orig = lambda q, k, v, cache=None, scale=None, mask=None, **kw: q
    return lk


def test_a_prompt_chunk_is_not_looked_at_and_a_written_word_is_worked_out_at_once():
    lk = looks(prompt_len=6)
    cache = "cache"
    q = mx.ones((1, 4, 1, 8))
    lk._spy(q, mx.ones((1, 2, 5, 8)), None, cache, 0.1, None)  # 5 keys: still the prompt
    assert not lk.calls
    lk._spy(q, mx.ones((1, 2, 6, 8)), None, cache, 0.1, None)  # the first written word
    got = lk.calls[6][12]
    assert got.shape == (2,) and abs(float(got[0]) - 2 / 6) < 1e-5 and abs(float(got[1]) - 1 / 6) < 1e-5
    assert lk.per_word(1).shape == (1, 2)
