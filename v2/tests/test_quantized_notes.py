"""Notes kept at 8 or 4 bits on the SSD: a token stays a fixed size, a room's file still grows by appending, rooms
written at 16 bits before still read, and the tiers count each room's file at its own size. The packing itself needs
MLX (the Mac); no model is loaded."""

from __future__ import annotations

import json

import numpy as np
import pytest

from camr_engine.notes import Shape, stored_bytes
from camr_engine.rooms import Rooms, room_file, room_id
from camr_engine.swap import Tiers

SHAPE = Shape(layers=3, kv_heads=2, head_dim=128, rope_base=1e6)
TB = SHAPE.token_bytes  # 3 × 2 × 2 × 128 × 2 = 3072


def unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_a_token_at_8_bits_is_17_32_of_its_16_bit_size_and_at_4_bits_9_32():
    assert stored_bytes(TB, 16) == TB
    assert stored_bytes(TB, 8) * 32 == TB * 17
    assert stored_bytes(TB, 4) * 32 == TB * 9
    assert stored_bytes(114688, 8) == 60928  # Qwen3-1.7B: 112 KB a token, 59.5 KB at 8 bits
    with pytest.raises(ValueError):
        stored_bytes(TB, 3)


@pytest.mark.parametrize("bits,most", [(8, 0.02), (4, 0.3)])
def test_packed_notes_come_back_close_and_tokens_stand_alone(bits, most):
    mx = pytest.importorskip("mlx.core")
    from camr_engine.notes import pack, unpack

    x = mx.random.normal((5, SHAPE.layers, 2, SHAPE.kv_heads, SHAPE.head_dim), key=mx.random.key(0)).astype(mx.bfloat16)
    buf = pack(x, bits)
    assert len(buf) == 5 * stored_bytes(TB, bits)
    back = unpack(buf, SHAPE, mx.bfloat16, bits)
    assert back.shape == x.shape and back.dtype == mx.bfloat16
    err = mx.abs(back.astype(mx.float32) - x.astype(mx.float32)).max().item()
    assert err < most * mx.abs(x).max().item()
    # packing two moments one after the other gives the bytes of packing them together: a room grows by appending
    assert pack(x[:2], bits) + pack(x[2:], bits) == buf
    assert mx.array_equal(unpack(pack(x, 16), SHAPE, mx.bfloat16, 16), x).item()


def test_new_rooms_take_the_memorys_bits_and_say_so_in_their_name(tmp_path):
    rooms = Rooms(tmp_path, TB, room_tokens=100, join=0.8, bits=8)
    size = stored_bytes(TB, 8)
    m = rooms.add("Amina moved to Nakuru.", 0, unit(1, 0), bytes([1]) * (10 * size), None)
    assert (m.tokens, rooms.rooms[m.room].bits) == (10, 8)
    assert rooms.file(m.room) == room_file(tmp_path, m.room, 8) == tmp_path / "room-000000.q8.notes"
    assert room_id(rooms.file(m.room)) == 0 and rooms.file(m.room).stat().st_size == 10 * size
    assert rooms.room_bytes(m.room) == 10 * size and rooms.disk_bytes() == 10 * size
    assert rooms.fetch([m.room])[m.room] == bytes([1]) * (10 * size)


def test_rooms_written_at_16_bits_before_still_read_and_keep_their_bits(tmp_path):
    old = Rooms(tmp_path, TB, room_tokens=100, join=0.8)
    a = old.add("old", 0, unit(1, 0), bytes([2]) * (4 * TB), None)
    old.save()
    index = json.loads((tmp_path / "index.json").read_text())
    for r in index["rooms"]:  # an index from before rooms kept their bits
        del r["bits"]
    (tmp_path / "index.json").write_text(json.dumps(index))
    rooms = Rooms(tmp_path, TB, room_tokens=100, join=0.8, bits=8)
    assert rooms.bits_of(a.room) == 16 and rooms.file(a.room).name == "room-000000.notes"
    assert rooms.fetch([a.room])[a.room] == bytes([2]) * (4 * TB)
    # a moment joining the old room is appended at 16 bits; a new room is started at 8
    b = rooms.add("joins", 1, unit(1, 0.01), bytes([3]) * (2 * TB), a.room)
    c = rooms.add("new", 1, unit(0, 1), bytes([4]) * (2 * stored_bytes(TB, 8)), None)
    assert (b.tokens, rooms.room_bytes(a.room)) == (2, 6 * TB)
    assert rooms.bits_of(c.room) == 8 and rooms.room_bytes(c.room) == 2 * stored_bytes(TB, 8)
    rooms.save()
    again = Rooms(tmp_path, TB, room_tokens=100, join=0.8)
    assert [r.bits for r in again.rooms] == [16, 8]


def test_the_disk_budget_counts_each_room_at_its_own_size(tmp_path):
    rooms = Rooms(tmp_path, TB, room_tokens=1000, join=0.99, bits=8)
    size = stored_bytes(TB, 8)
    for i in range(4):
        rooms.add(f"m{i}", i, unit(1, i), bytes([i]) * (10 * size), None)
    tiers = Tiers(disk_bytes=25 * size).bind(rooms)
    assert tiers.disk_bytes() == 40 * size
    slept = tiers.enforce()
    assert len(slept) == 2 and tiers.disk_bytes() == 20 * size
    assert all(not rooms.file(r).exists() for r in slept)
    assert tiers.load(3).bytes == 10 * size


def _reach_at_16_bits(folder, mx, n=3):
    """A reach folder with ``n`` 16-bit rooms of made-up notes, and a model folder whose config gives their shape."""
    from camr_engine.notes import pack

    model = folder / "model"
    model.mkdir()
    (model / "config.json").write_text(json.dumps({"num_hidden_layers": SHAPE.layers, "num_key_value_heads": 2,
                                                   "head_dim": 128, "hidden_size": 256, "num_attention_heads": 2,
                                                   "rope_theta": 1e6, "torch_dtype": "bfloat16"}))
    rooms = Rooms(folder / "reach", TB, room_tokens=100, join=0.99)
    xs = []
    for i in range(n):
        x = mx.random.normal((4 + i, SHAPE.layers, 2, 2, 128), key=mx.random.key(i)).astype(mx.bfloat16)
        rooms.add(f"m{i}", i, unit(1, i), pack(x, 16), None)
        xs.append(x)
    rooms.save()
    return folder / "reach", model, xs


def test_shrink_packs_a_reach_in_place_after_checking_each_copy(tmp_path):
    mx = pytest.importorskip("mlx.core")
    from camr_engine.notes import unpack
    from camr_engine.shrink import shrink

    reach, model, xs = _reach_at_16_bits(tmp_path, mx)
    before = sorted(p.name for p in reach.iterdir())
    dry = shrink(reach, 8)
    assert dry["to_pack"] == [0, 1, 2] and dry["bytes_after"] * 32 == dry["bytes_now"] * 17
    assert sorted(p.name for p in reach.iterdir()) == before  # a dry run changes nothing
    got = shrink(reach, 8, model=str(model), apply=True, progress=lambda *_: None)
    assert got["packed"] == 3 and got["bytes_on_disk"] == dry["bytes_after"]
    assert not list(reach.glob("room-??????.notes")) and len(list(reach.glob("room-*.q8.notes"))) == 3
    rooms = Rooms(reach, TB, room_tokens=100, join=0.99)
    assert [r.bits for r in rooms.rooms] == [8, 8, 8]
    for rid, x in enumerate(xs):
        back = unpack(rooms.fetch([rid])[rid], SHAPE, mx.bfloat16, 8)
        assert mx.abs(back.astype(mx.float32) - x.astype(mx.float32)).max().item() < 0.05
    assert shrink(reach, 8, model=str(model), apply=True)["packed"] == 0  # a second run has nothing to do


def test_shrink_finishes_a_stopped_run_and_refuses_an_open_reach(tmp_path):
    import fcntl
    import os

    mx = pytest.importorskip("mlx.core")
    from camr_engine.notes import pack, unpack
    from camr_engine.shrink import shrink

    reach, model, xs = _reach_at_16_bits(tmp_path, mx, n=2)
    # stopped after the index moved, before room 0's old file was deleted
    (reach / "room-000000.q8.notes").write_bytes(pack(unpack(pack(xs[0], 16), SHAPE, mx.bfloat16, 16), 8))
    index = json.loads((reach / "index.json").read_text())
    index["rooms"][0]["bits"] = 8
    (reach / "index.json").write_text(json.dumps(index))
    fd = os.open(reach / ".lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(RuntimeError):
            shrink(reach, 8, model=str(model), apply=True)
    finally:
        os.close(fd)
    assert shrink(reach, 8)["leftover_16bit"] == [0]
    got = shrink(reach, 8, model=str(model), apply=True, progress=lambda *_: None)
    assert got["packed"] == 1 and not (reach / "room-000000.notes").exists()
    assert sorted(p.name for p in reach.glob("room-*.notes")) == ["room-000000.q8.notes", "room-000001.q8.notes"]


def test_each_reach_gets_8_gb_unless_the_environment_says_otherwise(monkeypatch):
    from camr_engine.shelves import disk_budget

    monkeypatch.delenv("CAMR_SHELF_DISK_GB", raising=False)
    assert disk_budget() == 8 * 2**30
    monkeypatch.setenv("CAMR_SHELF_DISK_GB", "24")
    assert disk_budget() == 24 * 2**30
    monkeypatch.setenv("CAMR_SHELF_DISK_GB", "lots")
    assert disk_budget() == 8 * 2**30


def test_holding_the_budget_puts_cold_rooms_to_sleep_and_saves(tmp_path):
    from camr_engine.shelves import hold

    rooms = Rooms(tmp_path, TB, room_tokens=1000, join=0.99)
    for i in range(3):
        rooms.add(f"m{i}", i, unit(1, i), bytes([i]) * (10 * TB), None)

    class Kept:  # a memory as hold sees it: tiers, and save
        tiers = Tiers(disk_bytes=15 * TB).bind(rooms)
        saved = 0

        def save(self):
            Kept.saved += 1

    told = []
    got = hold({"global": Kept(), "none": object()}, lambda kind, **k: told.append((kind, k["slept"])))
    assert got == {"global": [0, 1]} and Kept.saved == 1 and told == [("budget", 2)]
    assert hold({"global": Kept()}) == {}  # held already: nothing more sleeps
