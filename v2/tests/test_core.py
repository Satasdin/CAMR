"""The core: core-tagged vault notes written once as notes, kept in RAM, and laid on every desk after the header and
before the room. Needs MLX (the Mac) for its arrays; no model is loaded: the reader here is a fake whose notes on a
token are just that token's number.

The fakes below are shared by test_swap, test_reach and test_metrics."""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
import time
import zlib
from types import SimpleNamespace

import numpy as np
import pytest

from engram.models import Reply

needs_mlx = pytest.mark.skipif(importlib.util.find_spec("mlx") is None, reason="needs MLX (the Mac)")
TODAY = dt.date(2026, 1, 20)


class FakeTok:
    """One token per character, so token counts are easy to check."""

    def apply_chat_template(self, msgs, tools=None, add_generation_prompt=True, enable_thinking=False, tokenize=False):
        return "".join(f"<{m['role']}>{m['content']}</{m['role']}>" for m in msgs) + "<assistant>"

    def encode(self, text: str) -> list[int]:
        return [ord(c) % 1000 + 1 for c in text]


class FakeModel:
    """Writes, at every layer, keys and values equal to the token's number (plus the layer): no context, no
    position, so where each note lands on the desk can be read straight off its values."""

    def __init__(self, layers: int = 2, heads: int = 1, dim: int = 4):
        self.layers = [None] * layers
        self.args = SimpleNamespace(num_key_value_heads=heads, head_dim=dim, rope_theta=10000.0, rope_scaling=None)

    def __call__(self, x, cache=None):
        import mlx.core as mx

        a = self.args
        v = x[0].astype(mx.float16)[None, None, :, None] * mx.ones((1, a.num_key_value_heads, 1, a.head_dim),
                                                                   dtype=mx.float16)
        for i, c in enumerate(cache):
            c.update_and_fetch(v + i, v + i)
        return mx.zeros((1, x.shape[1], 8))


class FakeReader:
    repo = "fake"

    def __init__(self):
        self.tok, self.model, self.calls = FakeTok(), FakeModel(), []

    def new_cache(self, ids):
        import mlx.core as mx
        from mlx_lm.models.cache import KVCache

        cache = [KVCache() for _ in self.model.layers]
        self.model(mx.array(ids)[None], cache=cache)
        return cache

    def chat_ids(self, system, user, tools=None):
        return self.tok.encode(self.tok.apply_chat_template([{"role": "system", "content": system},
                                                             {"role": "user", "content": user}]))

    def generate(self, ids, cache=None, max_tokens=None):
        """Takes 2 ms, the first word after 1 ms, like a (very fast) real reader."""
        self.calls.append(SimpleNamespace(ids=list(ids), offset=cache[0].offset if cache else 0, cache=cache))
        time.sleep(0.002)
        return Reply("ok", 0.001, 100.0, len(ids), 2, ["o", "k"])


STOP = {"the", "a", "my", "to", "is", "in", "of", "does", "what", "where", "when", "was", "how", "much"}


class FakeEmbedder:
    """Bag of words: moments and questions sharing words are close."""

    def encode_one(self, text: str, *, is_query: bool = False) -> np.ndarray:
        v = np.zeros(4096, np.float32)
        for w in re.findall(r"[a-z]+", text.lower()):
            if w not in STOP:
                v[zlib.crc32(w.encode()) % 4096] += 1
        n = np.linalg.norm(v)
        return v / n if n else v


def make(path, **kw):
    from engram.memory import Memory

    settings = {"log": False, "room_tokens": 400, "join": 0.2, **kw}
    return Memory(FakeReader(), FakeEmbedder(), path, **settings)


def desk_values(cache) -> np.ndarray:
    """The first value number of every token on a desk (layer 0)."""
    import mlx.core as mx

    return np.array(cache[0].values[0, 0, :cache[0].offset, 0].astype(mx.float32))


def numbers(text: str) -> list[float]:
    return [float(ord(c) % 1000 + 1) for c in text + "\n"]


# -- the core


@needs_mlx
def test_the_core_is_built_from_core_tagged_notes_and_kept_in_ram(tmp_path):
    from engram.vault import Vault

    m = make(tmp_path / "memory", vault=True, core=True)
    m.vault.write("I am Ibrahim.", tags=["core"], pinned=True)
    m.vault.write("Not part of the core.")
    assert m.core.refresh() and m.core.tokens == len("I am Ibrahim.\n") and m.core.writes == 1
    assert m.core.notes.shape == (m.core.tokens, 2, 2, 1, 4)
    assert m.core.bytes == m.core.tokens * m.notebook.shape.token_bytes and m.core.text() == "I am Ibrahim."
    assert isinstance(m.vault, Vault) and not m.core.refresh()  # nothing changed: not written again


@needs_mlx
def test_the_core_is_written_again_only_when_its_notes_change(tmp_path):
    m = make(tmp_path / "memory", vault=True, core=True)
    a = m.vault.write("I am Ibrahim.", day=0, tags=["core"])
    m.core.refresh()
    m.vault.fade(5)  # strength changes; words do not
    assert not m.core.refresh() and m.core.writes == 1
    m.vault.write("I live in Nairobi.", day=1, tags=["core"])
    assert m.core.refresh() and m.core.writes == 2 and m.core.text() == "I am Ibrahim.\nI live in Nairobi."
    m.vault.untag(a.id, "core")
    assert m.core.refresh() and m.core.members == ["m-note-0002"]


@needs_mlx
def test_the_core_keeps_to_its_budget_pinned_notes_first(tmp_path):
    m = make(tmp_path / "memory", vault=True, core=True, core_tokens=30)
    m.vault.write("A long standing fact that will not fit with the rest.", day=0, tags=["core"])
    m.vault.write("I am Ibrahim.", day=1, tags=["core"], pinned=True)
    m.core.refresh()
    assert m.core.members == ["m-note-0002"] and m.core.left_out == ["m-note-0001"] and m.core.tokens <= 30


@needs_mlx
def test_the_core_goes_after_the_header_and_before_the_room(tmp_path):
    m = make(tmp_path / "memory", vault=True, core=True)
    m.remember("Amina moved to Nakuru.", 0)
    m.remember("Amina adopted a dog called Simba.", 1)
    m.vault.write("I am Ibrahim.", tags=["core"], pinned=True)
    rec = m.recall("Where does Amina live?")
    p, c = m.notebook.p, len("I am Ibrahim.\n")
    assert rec.core == c and rec.desk[0].offset == p + c + rec.tokens and "core" in rec.seconds
    values = desk_values(rec.desk)
    assert values[p:p + c].tolist() == numbers("I am Ibrahim.")
    assert values[p + c:].tolist() == numbers("Amina moved to Nakuru.") + numbers("Amina adopted a dog called Simba.")
    # the room was written straight after the header: on the desk its keys are turned along by the core's length
    import mlx.core as mx

    from engram.notes import turn

    raw = m._array(m.rooms.fetch([0])[0]).transpose(1, 2, 3, 0, 4)  # (layers, 2, heads, tokens, dim)
    n = rec.tokens
    for layer, cache in enumerate(rec.desk):
        want = turn(raw[layer, 0], mx.full((n,), c, dtype=mx.int32), m.notebook.shape.rope_base)
        got = cache.keys[0, :, p + c:p + c + n, :]
        assert np.allclose(np.array(got.astype(mx.float32)), np.array(want.astype(mx.float32)), atol=1e-3)
        assert not np.allclose(np.array(got.astype(mx.float32)), np.array(raw[layer, 0].astype(mx.float32)))
        assert (np.array(cache.values[0, :, p + c:].astype(mx.float32))
                == np.array(raw[layer, 1].astype(mx.float32))).all()  # values carry no position


@needs_mlx
def test_an_answer_reads_its_words_after_the_core_and_the_room(tmp_path):
    m = make(tmp_path / "memory", vault=True, core=True)
    m.remember("Amina moved to Nakuru.", 0)
    m.vault.write("I am Ibrahim.", tags=["core"])
    reply = m.answer("Where does Amina live?", TODAY)
    call = m.reader.calls[-1]
    head, rest = m.prompt(TODAY, "Where does Amina live?")
    c, r = len("I am Ibrahim.\n"), len("Amina moved to Nakuru.\n")
    assert call.offset == m.notebook.p + c + r
    assert call.ids == m.ids("Amina moved to Nakuru.") + rest
    assert reply.prompt_tokens == len(head) + c + r + len(call.ids)


@needs_mlx
def test_without_core_notes_the_desk_is_as_before(tmp_path):
    m = make(tmp_path / "memory", vault=True, core=True)
    m.remember("Amina moved to Nakuru.", 0)
    rec = m.recall("Where does Amina live?")
    assert rec.core == 0 and rec.desk[0].offset == m.notebook.p + rec.tokens


def test_a_core_needs_a_vault(tmp_path):
    pytest.importorskip("mlx")
    with pytest.raises(ValueError):
        make(tmp_path / "memory", core=True)


@needs_mlx
def test_a_core_note_edited_added_or_deleted_by_hand_changes_the_core_without_reopening(tmp_path):
    m = make(tmp_path / "memory", vault=True, core=True)
    m.remember("Amina moved to Nakuru.", 0)
    me = m.vault.write("I am Ibrahim.", day=0, tags=["core"], pinned=True)
    m.recall("Where does Amina live?")
    assert m.core.text() == "I am Ibrahim." and m.core.writes == 1
    f = m.vault.file(me.id)
    f.write_text(f.read_text().replace("I am Ibrahim.", "I am Ibrahim. I live in Mombasa."))  # edited in place
    rec = m.recall("Where does Amina live?")
    assert m.core.text() == "I am Ibrahim. I live in Mombasa." and m.core.writes == 2
    assert rec.core == len("I am Ibrahim. I live in Mombasa.\n")
    m.vault.file("persona").write_text("---\ntags: [core]\nday: 1\n---\nI build memory for small models.\n")
    m.recall("Where does Amina live?")
    assert m.core.members == [me.id, "persona"] and m.core.writes == 3
    m.vault.file("persona").unlink()
    m.recall("Where does Amina live?")
    assert m.core.members == [me.id] and "persona" not in m.vault and m.core.writes == 4
    m.recall("Where does Amina live?")
    assert m.core.writes == 4  # nothing changed: not written again


class StubLooks:
    """Looks without a Qwen3 model: every written word looks equally at every node on the desk."""

    def __init__(self, reader, header, spans, prompt_len, desk):
        self.nodes = sorted({n for n, _, _ in spans})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def per_word(self, words: int) -> np.ndarray:
        return np.ones((words, len(self.nodes)), dtype=np.float32)


@needs_mlx
def test_notes_used_in_one_answer_gain_strength_and_their_doors_strengthen(tmp_path, monkeypatch):
    import engram.memory
    from engram.vault import FADE, SHARE, TOGETHER, USE

    monkeypatch.setattr(engram.memory, "Looks", StubLooks)
    m = make(tmp_path / "memory", vault=True, log=True)
    a = m.remember("Amina moved to Nakuru.", 0)
    b = m.remember("Amina adopted a dog called Simba.", 1)
    ia, ib = m.vault.moment_id(a.mid), m.vault.moment_id(b.mid)
    assert a.room == b.room and m.vault.neighbours(ia) == [(ib, SHARE)]
    m.answer("Where does Amina live?", TODAY, day=3)
    event = m.log.read()[-1]
    assert event["type"] == "answer" and event["used"] == [0, 1]
    na, nb = m.vault.read(ia), m.vault.read(ib)
    assert na.used == nb.used == 3 and na.as_of == nb.as_of == 3
    assert na.strength == pytest.approx((1 - FADE) ** 3 + USE, abs=1e-4)
    assert nb.strength == pytest.approx((1 - FADE) ** 2 + USE, abs=1e-4)
    assert m.vault.neighbours(ia) == [(ib, SHARE + TOGETHER)] and m.vault.neighbours(ib) == [(ia, SHARE + TOGETHER)]
