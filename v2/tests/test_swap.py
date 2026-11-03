"""The tiers: hot rooms in RAM inside a budget, awake rooms on the SSD, and asleep rooms kept only as words. The first
tests use made-up bytes and no model; the last ones go through Memory with the fake reader (needs MLX)."""

from __future__ import annotations

import numpy as np
import pytest

from engram.rooms import Rooms
from engram.swap import RAM, SSD, VAULT, Pool, Tiers

TB = 16  # bytes per token in these tests


def unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def filled(tmp_path, sizes: list[int], name: str = "memory") -> Rooms:
    """One room per size (tokens), each its own topic, notes made of the room's number."""
    rooms = Rooms(tmp_path / name, TB, room_tokens=1000, join=0.99)
    for i, n in enumerate(sizes):
        rooms.add(f"moment {i}", i, unit(*np.eye(len(sizes))[i]), bytes([i + 1]) * (n * TB), None)
    rooms.save()
    return rooms


def test_a_room_comes_from_the_ssd_once_and_then_from_ram(tmp_path):
    rooms = filled(tmp_path, [10, 20])
    tiers = Tiers(ram_bytes=10**6).bind(rooms)
    first, second = tiers.load(0), tiers.load(0)
    assert first.tier == SSD and first.bytes == 10 * TB and first.seconds > 0 and first.gbps > 0
    assert second.tier == RAM and second.bytes == 0 and second.gbps is None
    assert bytes(second.data) == bytes([1]) * (10 * TB) and tiers.hits == {SSD: 1, RAM: 1}


def test_ram_keeps_the_most_recently_used_rooms_inside_its_budget(tmp_path):
    rooms = filled(tmp_path, [10, 10, 10])
    tiers = Tiers(ram_bytes=25 * TB).bind(rooms)
    tiers.load(0), tiers.load(1), tiers.load(0), tiers.load(2)  # room 1 is now the least recently used
    assert list(tiers.hot) == [0, 2] and tiers.ram_bytes() == 20 * TB
    tiers.core_bytes = 10 * TB  # the core always stays, so fewer rooms fit beside it
    tiers.load(1)
    assert list(tiers.hot) == [1] and tiers.ram_bytes() == 20 * TB
    big = Tiers(ram_bytes=5 * TB).bind(rooms)
    assert big.load(0).tier == SSD and not big.hot  # a room bigger than RAM's budget is never kept


def test_a_room_too_big_for_ram_pushes_no_other_room_out(tmp_path):
    rooms = filled(tmp_path, [10, 10, 30])
    tiers = Tiers(ram_bytes=25 * TB).bind(rooms)
    tiers.load(0), tiers.load(1)
    assert tiers.load(2).tier == SSD and list(tiers.hot) == [0, 1] and tiers.ram_bytes() == 20 * TB
    assert tiers.load(2).tier == SSD  # and it is read from the SSD every time


def test_memories_sharing_a_pool_share_one_ram_budget_with_the_core_counted_once(tmp_path):
    a, b = filled(tmp_path, [10, 10], "a"), filled(tmp_path, [10], "b")
    pool = Pool(25 * TB)
    ta, tb = Tiers(pool=pool).bind(a), Tiers(ram_bytes=10**9, pool=pool).bind(b)
    ta.load(0), tb.load(0)
    assert list(ta.hot) == [0] and list(tb.hot) == [0] and ta.ram_bytes() == tb.ram_bytes() == 20 * TB
    ta.load(1)  # the least recently used room in the pool goes, whichever memory it is in
    assert list(ta.hot) == [1] and list(tb.hot) == [0] and pool.used_bytes() == 20 * TB
    tb.core_bytes = 10 * TB  # set through either memory, it is one core in one budget
    assert ta.core_bytes == 10 * TB and pool.used_bytes() == 20 * TB and list(ta.hot) == [1] and not tb.hot
    assert tb.load(0).tier == SSD and list(tb.hot) == [0] and not ta.hot and pool.used_bytes() == 20 * TB


def test_past_the_disk_budget_the_weakest_least_recently_used_rooms_go_to_sleep(tmp_path):
    rooms = filled(tmp_path, [10, 10, 10, 10])
    told = []
    strength = {0: 1.0, 1: 0.2, 2: 1.0, 3: 1.0}
    tiers = Tiers(disk_bytes=25 * TB).bind(rooms, strength=strength.get, notify=lambda r, a: told.append((r, a)))
    tiers.load(2), tiers.load(0), tiers.load(3)  # room 2 is the least recently used of the strong ones
    assert tiers.enforce() == [1, 2]
    assert told == [([1, 2], True)] and tiers.sleeping == {1, 2}
    assert not rooms.file(1).exists() and not rooms.file(2).exists() and rooms.disk_bytes() == 20 * TB
    assert [m.text for m in rooms.moments] == ["moment 0", "moment 1", "moment 2", "moment 3"]  # words stay
    assert tiers.load(1) == tiers.load(1) and tiers.load(1).tier == VAULT and tiers.load(1).data is None
    assert tiers.state()["vault"]["rooms"] == [1, 2] and tiers.disk_bytes() == 20 * TB


def test_an_asleep_room_wakes_from_its_words_when_waking_is_on(tmp_path):
    rooms = filled(tmp_path, [10, 12])
    tiers = Tiers(wake=True).bind(rooms, rewrite=lambda rid: bytes([9]) * (rooms.rooms[rid].tokens * TB),
                                  notify=lambda r, a: None)
    tiers.sleep(1)
    got = tiers.load(1)
    assert got.tier == VAULT and got.woke and got.wake_s >= 0 and bytes(got.data) == bytes([9]) * (12 * TB)
    assert rooms.file(1).exists() and 1 not in tiers.sleeping and bytes(rooms.fetch([1])[1]) == bytes(got.data)


def test_waking_a_room_holds_the_disk_budget_and_keeps_the_woken_room_awake(tmp_path):
    rooms = filled(tmp_path, [10, 10, 10])
    told = []
    tiers = Tiers(disk_bytes=20 * TB, wake=True).bind(
        rooms, rewrite=lambda rid: bytes([9]) * (rooms.rooms[rid].tokens * TB), notify=lambda r, a: told.append((r, a)))
    assert tiers.enforce() == [0]
    got = tiers.load(0)
    assert got.woke and 0 not in tiers.sleeping and tiers.sleeping == {1}
    assert tiers.disk_bytes() == rooms.disk_bytes() == 20 * TB and told == [([0], True), ([0], False), ([1], True)]


def test_a_woken_room_must_come_back_its_own_size(tmp_path):
    rooms = filled(tmp_path, [10])
    tiers = Tiers(wake=True).bind(rooms, rewrite=lambda rid: b"short")
    tiers.sleep(0)
    with pytest.raises(ValueError):
        tiers.load(0)


def test_new_notes_keep_a_hot_room_current(tmp_path):
    rooms = filled(tmp_path, [10])
    tiers = Tiers().bind(rooms, join=lambda a, b: bytes(a) + b)
    tiers.load(0)
    tiers.wrote(0, bytes([7]) * (2 * TB), 2 * TB)
    assert tiers.hot[0] == bytes([1]) * (10 * TB) + bytes([7]) * (2 * TB) and tiers.sizes[0] == 12 * TB
    plain = Tiers().bind(rooms)
    plain.load(0)
    plain.wrote(0, b"x", 1)
    assert 0 not in plain.hot  # without a way to append, the stale copy is dropped


def test_asleep_rooms_and_use_order_survive_reopening(tmp_path):
    rooms = filled(tmp_path, [10, 10])
    tiers = Tiers().bind(rooms)
    tiers.load(1)
    tiers.sleep(0)
    tiers.save()
    again = Tiers().bind(Rooms(tmp_path / "memory", TB, room_tokens=1000, join=0.99))
    assert again.sleeping == {0} and again.used == tiers.used and again.tick == tiers.tick


# -- through Memory, with the fake reader


def test_memory_answers_an_asleep_room_from_its_moments_as_words(tmp_path):
    pytest.importorskip("mlx")
    from test_core import TODAY, make

    m = make(tmp_path / "memory", tiers=Tiers(disk_bytes=0))
    m.remember("Amina moved to Nakuru.", 0)
    m.remember("Amina adopted a dog called Simba.", 1)
    assert m.tiers.sleeping == {0, 1} and m.rooms.disk_bytes() == 0  # the second could not join an asleep room
    head, rest = m.prompt(TODAY, "Where does Amina live?")
    reply = m.answer("Where does Amina live?", TODAY)
    call, rec = m.reader.calls[-1], m.choose("Where does Amina live?")
    assert rec.room == 0 and rec.closest == [0, 1]
    assert call.offset == m.notebook.p  # nothing but the header on the desk
    assert call.ids == m.room_words(0) + m.words([0, 1]) + rest and reply.prompt_tokens == len(head) + len(call.ids)


def test_a_moment_for_an_asleep_room_starts_a_room_of_its_own(tmp_path):
    pytest.importorskip("mlx")
    from test_core import make

    m = make(tmp_path / "memory", tiers=Tiers(), vault=True)
    a = m.remember("Amina moved to Nakuru.", 0)
    later = "Amina adopted a dog called Simba."
    assert m.rooms.place(m.embedder.encode_one(later), len(m.ids(later))) == a.room  # it belongs there
    m.tiers.sleep(a.room)
    assert m.vault.get(m.vault.moment_id(a.mid)).asleep
    b = m.remember(later, 1)
    assert b.room != a.room and b.start == 0


def test_memory_wakes_an_asleep_room_and_lays_its_notes_as_they_were(tmp_path):
    pytest.importorskip("mlx")
    from test_core import desk_values, make

    m = make(tmp_path / "memory", tiers=Tiers(wake=True), vault=True)
    m.remember("Amina moved to Nakuru.", 0)
    m.remember("Amina adopted a dog called Simba.", 1)
    assert len(m.rooms.rooms) == 1
    before = bytes(m.rooms.fetch([0])[0])
    awake = desk_values(m.recall("Where does Amina live?").desk)
    m.tiers.sleep(0)
    rec = m.recall("Where does Amina live?")
    assert rec.tier == VAULT and not rec.asleep and "wake" in rec.seconds
    assert bytes(m.rooms.fetch([0])[0]) == before and (desk_values(rec.desk) == awake).all()
    assert not m.vault.get(m.vault.moment_id(0)).asleep


def test_every_recall_reports_its_tier_bytes_and_bandwidth(tmp_path):
    pytest.importorskip("mlx")
    from test_core import make

    m = make(tmp_path / "memory", tiers=Tiers())
    m.remember("Amina moved to Nakuru.", 0)
    m.tiers.forget(0)
    first = m.recall("Where does Amina live?")
    second = m.recall("Where does Amina live?")
    assert first.tier == SSD and first.read_bytes == first.bytes and first.gbps is not None
    assert second.tier == RAM and second.read_bytes == 0 and set(second.seconds) >= {"choose", "fetch", "desk"}
    plain = make(tmp_path / "plain")  # without tiers every room comes from the SSD, as before
    plain.remember("Amina moved to Nakuru.", 0)
    rec = plain.recall("Where does Amina live?")
    assert rec.tier == SSD and rec.read_bytes == rec.bytes


def test_a_memory_with_every_layer_on_keeps_its_budgets_and_reopens_where_it_left_off(tmp_path):
    pytest.importorskip("mlx")
    from test_core import TODAY, make

    def open_():
        return make(tmp_path / "memory", vault=True, core=True, metrics=True, room_tokens=120,
                    tiers=Tiers(ram_bytes=6_000, disk_bytes=8_000))

    m = open_()
    m.vault.write("I am Ibrahim.", day=0, tags=["core"], pinned=True)
    for day, topic in enumerate(["amina nakuru", "simba dog", "electricity bill", "toyota vitz"] * 4):
        m.remember(f"Day {day}: something about {topic}.", day)
        m.fade(day)
        m.answer(f"What about {topic}?", TODAY, day=day)
    assert m.rooms.disk_bytes() == m.tiers.disk_bytes() <= 8_000 and m.tiers.ram_bytes() <= 6_000
    assert m.tiers.sleeping and {r.tier for r in m.meter.records} >= {"ram", "vault"}
    asleep = {n.moment for n in m.vault.notes() if n.asleep}
    assert asleep == {mid for rid in m.tiers.sleeping for mid in m.rooms.rooms[rid].members}
    m.save()
    m.close()
    again = open_()
    assert again.tiers.sleeping == m.tiers.sleeping and len(again.vault) == len(m.vault) == 17
    for room in again.rooms.rooms:  # an asleep room has no file; an awake one is exactly its index's size
        f = again.rooms.file(room.rid)
        assert f.exists() == (room.rid not in again.tiers.sleeping)
        assert not f.exists() or f.stat().st_size == room.tokens * again.rooms.token_bytes
    assert again.answer("What about simba dog?", TODAY).metrics.context_tokens > 0


def test_a_vault_note_deleted_by_hand_never_breaks_remembering_fading_or_sleeping(tmp_path):
    pytest.importorskip("mlx")
    from test_core import TODAY, desk_values, make

    m = make(tmp_path / "memory", vault=True, tiers=Tiers(disk_bytes=10**6))
    a = m.remember("Amina moved to Nakuru.", 0)
    m.recall("Where does Amina live?")  # the room is hot now
    m.vault.file(m.vault.moment_id(a.mid)).unlink()
    b = m.remember("Amina adopted a dog called Simba.", 1)
    assert b.room == a.room and len(m.rooms.moments) == 2
    assert m.fade(5) == (1, [])  # the deleted note is forgotten; the other fades
    assert m.vault.moment_id(a.mid) not in m.vault and len(m.vault) == 1
    awake = desk_values(m.recall("Where does Amina live?").desk)
    m.tiers.forget(a.room)
    assert (desk_values(m.recall("Where does Amina live?").desk) == awake).all()  # the hot copy matched the file
    m.tiers.sleep(a.room)
    assert m.vault.get(m.vault.moment_id(b.mid)).asleep
    m.answer("Where does Amina live?", TODAY, day=6)


def test_the_hot_copy_matches_the_room_file_even_when_the_vault_fails(tmp_path, monkeypatch):
    pytest.importorskip("mlx")
    from test_core import desk_values, make

    m = make(tmp_path / "memory", vault=True, tiers=Tiers())
    m.remember("Amina moved to Nakuru.", 0)
    m.recall("Where does Amina live?")

    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(m, "_note", broken)
    with pytest.raises(OSError):
        m.remember("Amina adopted a dog called Simba.", 1)
    hot = desk_values(m.recall("Where does Amina live?").desk)
    m.tiers.forget(0)
    assert (desk_values(m.recall("Where does Amina live?").desk) == hot).all()


def test_closing_a_memory_with_its_layers_on_keeps_what_it_remembered(tmp_path):
    pytest.importorskip("mlx")
    from test_core import make

    m = make(tmp_path / "memory", vault=True, tiers=Tiers())
    m.remember("The fee is 1% rounded up to the next 5 shillings.", 3, tags=["rule"])
    m.close()  # no save first
    again = make(tmp_path / "memory", vault=True, tiers=Tiers())
    assert len(again.rooms.moments) == 1 and again.vault.get("m-000000").tags == ["rule"]
