"""Rooms on disk: moments join the room of their closest moment, files only grow, and a fetch returns exact bytes.
No model is loaded: notes here are made-up bytes."""

from __future__ import annotations

import json

import numpy as np

from engram.rooms import Rooms

TB = 16  # bytes per token in these tests


def unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def notes(tokens: int, fill: int) -> bytes:
    return bytes([fill]) * (tokens * TB)


def put(rooms: Rooms, text: str, day: int, vec, data: bytes):
    return rooms.add(text, day, vec, data, rooms.place(vec, len(data) // TB))


def test_close_moments_share_a_room_and_far_ones_start_their_own(tmp_path):
    rooms = Rooms(tmp_path, TB, room_tokens=100, join=0.8)
    a = put(rooms, "Amina moved to Nakuru.", 0, unit(1, 0, 0), notes(10, 1))
    b = put(rooms, "Amina moved again, to Kisumu.", 3, unit(0.95, 0.1, 0), notes(12, 2))
    c = put(rooms, "Paid the electricity bill.", 4, unit(0, 0, 1), notes(8, 3))
    assert a.room == b.room != c.room
    assert (b.start, b.tokens) == (10, 12) and rooms.rooms[a.room].tokens == 22


def test_a_full_room_sends_the_moment_to_a_new_room(tmp_path):
    rooms = Rooms(tmp_path, TB, room_tokens=20, join=0.5)
    a = put(rooms, "one", 0, unit(1, 0), notes(15, 1))
    b = put(rooms, "two", 0, unit(1, 0.1), notes(10, 2))
    assert a.room != b.room and b.start == 0


def test_a_fetch_returns_each_room_byte_for_byte(tmp_path):
    rooms = Rooms(tmp_path, TB, room_tokens=10**6, join=0.9)
    rng = np.random.default_rng(0)
    written = {}
    for i in range(6):
        data = rng.integers(0, 256, size=(70_000 + i) * TB, dtype=np.uint8).tobytes()  # rooms over 1 MB
        m = put(rooms, f"moment {i}", i, unit(*np.eye(6)[i]), data)
        written.setdefault(m.room, b"")
        written[m.room] += data
    got = rooms.fetch(list(written))
    assert {rid: bytes(b) for rid, b in got.items()} == written


def test_the_index_is_saved_beside_the_rooms(tmp_path):
    rooms = Rooms(tmp_path, TB, room_tokens=100, join=0.8)
    put(rooms, "Amina moved to Nakuru.", 0, unit(1, 0), notes(3, 1))
    rooms.save()
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["moments"][0]["text"] == "Amina moved to Nakuru." and rooms.disk_bytes() == 3 * TB
    assert np.load(tmp_path / "vectors.npy").shape == (1, 2)
