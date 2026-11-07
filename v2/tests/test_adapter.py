"""The reading adapter (camr_engine.adapter): off it adds exactly nothing, it is on only for the question and the
answer, it saves and loads, and its training data never comes from the locked exam."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import mlx.nn as nn
import pytest

from camr_engine import adapter
from camr_engine.memory import Memory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import train_adapter  # noqa: E402


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(8, 8)

    def __call__(self, x):
        return self.proj(x)


class Toy(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = [Block() for _ in range(3)]

    def __call__(self, x):
        for b in self.layers:
            x = b(x)
        return x


def _toy():
    mx.random.seed(0)
    m = Toy()
    mx.eval(m.parameters())
    return m


def _nudge(model):
    for layer in adapter.lora_layers(model):
        layer.lora_b = mx.ones_like(layer.lora_b) * 0.1


def test_off_is_the_plain_model_bit_for_bit():
    m = _toy()
    x = mx.random.normal((2, 8))
    plain = m(x)
    got = adapter.attach(m, layers=2)
    assert len(got) == 2
    _nudge(m)
    adapter.switch(m, False)
    assert mx.array_equal(m(x), plain)
    adapter.switch(m, True)
    assert not mx.allclose(m(x), plain)
    with adapter.off(m):
        assert mx.array_equal(m(x), plain)
    assert adapter.is_on(m)
    adapter.switch(m, False)
    with adapter.on(m):
        assert adapter.is_on(m)
    assert not adapter.is_on(m)


def test_an_adapter_saves_and_loads(tmp_path):
    m = _toy()
    x = mx.random.normal((1, 8))
    adapter.attach(m, layers=2)
    _nudge(m)
    adapter.switch(m, True)
    want = m(x)
    adapter.save(m, tmp_path / "a", {"name": "a", "layers": 2, "config": adapter.CONFIG})
    fresh = _toy()
    meta = adapter.load(fresh, tmp_path / "a")
    assert meta["name"] == "a" and not adapter.is_on(fresh)
    with adapter.on(fresh):
        assert mx.allclose(fresh(x), want)


def test_memory_is_read_with_it_off_and_the_question_with_it_on():
    seen = []

    class Model:
        def __call__(self, ids, cache=None):
            seen.append(("read", ids.shape[1], adapter.is_on(m)))
            return ids

    m = _toy()
    adapter.attach(m, layers=1)
    m_call = Model()

    class Reader:
        model = m

        def generate(self, ids, cache=None, max_tokens=None):
            seen.append(("write", len(ids), adapter.is_on(m)))
            return SimpleNamespace(ttft_s=0.1)

    reader = Reader()
    # prefill calls the model itself: point it at the recording stand-in while keeping the LoRA layers to switch
    orig = adapter.prefill

    def prefill(model, ids, cache, step=2048):
        with adapter.off(model):
            m_call(mx.array(ids)[None])

    adapter.prefill = prefill
    try:
        fake = SimpleNamespace(adapter={"name": "x"}, reader=reader)
        reply = Memory._generate(fake, [1, 2, 3], [1, 2, 3, 9, 9], cache=[], max_tokens=5)
    finally:
        adapter.prefill = orig
    assert seen == [("read", 3, False), ("write", 2, True)]
    assert reply.ttft_s >= 0.1 and not adapter.is_on(m)
    seen.clear()
    fake.adapter = None
    Memory._generate(fake, [1, 2, 3], [1, 2, 3, 9, 9], cache=[], max_tokens=5)
    assert seen == [("write", 5, False)]


def test_training_never_reads_the_locked_exam(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"seed": 1}))
    with pytest.raises(SystemExit):
        train_adapter.examples_for(tmp_path, None)
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps({"seed": 3, "world": "s3", "cut": "1M"}) + "\n")
    with pytest.raises(SystemExit):
        train_adapter.load_rows(rows)


def test_targets_are_the_generators_answers():
    assert train_adapter.target({"family": "never", "answer": "(never said)"}) == "I don't know."
    assert train_adapter.target({"family": "fact", "answer": "3 km"}) == "3 km."
    assert train_adapter.target({"family": "changed", "answer": "9443"}) == "9443."
