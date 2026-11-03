"""Rooms: related moments kept side by side on the SSD, one file per room, fetched whole in one burst.

A room's file holds its moments' notes token by token (see engram.notes), so a moment joins a room by appending to
the end of its file. What a person reads (each moment's words, its day, its embedding) stays in a small index beside
the files. Every read and write bypasses the Mac's file cache, so a fetch is a real SSD read, never a copy in RAM.
"""

from __future__ import annotations

import fcntl
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

F_NOCACHE = 48  # macOS: don't keep this file's pages in RAM
CHUNK = 1 << 20  # reads go out as 1 MB pieces, eight at once: the SSD's fast pattern
THREADS = 8


@dataclass
class Moment:
    mid: int
    room: int
    day: int
    text: str
    start: int  # first token in its room's file
    tokens: int


@dataclass
class Room:
    rid: int
    members: list[int] = field(default_factory=list)
    tokens: int = 0


def _open(path: Path, flags: int) -> int:
    fd = os.open(path, flags, 0o644)
    try:
        fcntl.fcntl(fd, F_NOCACHE, 1)
    except OSError:  # not macOS: plain reads and writes
        pass
    return fd


class Rooms:
    """The memory on the SSD. ``token_bytes`` is the size of one token's notes; ``room_tokens`` caps a room; a moment
    joins the room holding its closest moment when that closeness is at least ``join``, otherwise it starts a room."""

    def __init__(self, path: Path, token_bytes: int, room_tokens: int, join: float):
        self.path, self.token_bytes, self.room_tokens, self.join = Path(path), token_bytes, room_tokens, join
        self.path.mkdir(parents=True, exist_ok=True)
        self.moments: list[Moment] = []
        self.rooms: list[Room] = []
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self._pool = ThreadPoolExecutor(THREADS)
        index = self.path / "index.json"
        if index.exists():  # an existing memory: pick up where it was saved
            saved = json.loads(index.read_text())
            if saved["token_bytes"] != token_bytes:
                raise ValueError("these rooms were written for a different model")
            self.moments = [Moment(**m) for m in saved["moments"]]
            self.rooms = [Room(**r) for r in saved["rooms"]]
            self.vectors = np.load(self.path / "vectors.npy")
            for room in self.rooms:  # notes appended after the last save belong to no moment: drop them
                f, size = self.file(room.rid), room.tokens * token_bytes
                if f.exists() and f.stat().st_size > size:
                    os.truncate(f, size)

    def file(self, rid: int) -> Path:
        return self.path / f"room-{rid:06d}.notes"

    def place(self, vec: np.ndarray, tokens: int) -> int | None:
        """The room a new moment belongs in, or None for a new room."""
        if not self.moments:
            return None
        sims = self.vectors @ vec
        for m in np.argsort(-sims):
            if sims[m] < self.join:
                return None
            room = self.rooms[self.moments[m].room]
            if room.tokens + tokens <= self.room_tokens:
                return room.rid
        return None

    def add(self, text: str, day: int, vec: np.ndarray, notes: bytes, rid: int | None) -> Moment:
        """Append a moment's notes to room ``rid`` (from ``place``), or to a new room when it is None."""
        tokens = len(notes) // self.token_bytes
        if rid is None:
            rid = len(self.rooms)
            self.rooms.append(Room(rid))
        room = self.rooms[rid]
        fd = _open(self.file(rid), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            os.write(fd, notes)
        finally:
            os.close(fd)
        m = Moment(len(self.moments), rid, day, text, room.tokens, tokens)
        room.members.append(m.mid)
        room.tokens += tokens
        self.moments.append(m)
        vec = vec.astype(np.float32)[None]
        self.vectors = vec if not self.vectors.size else np.concatenate([self.vectors, vec])
        return m

    def fetch(self, rids: list[int]) -> dict[int, bytearray]:
        """Each room's whole file, read from the SSD in one burst of 1 MB pieces."""
        out, jobs = {}, []
        fds = {}
        for rid in rids:
            size = self.rooms[rid].tokens * self.token_bytes
            out[rid] = bytearray(size)
            fds[rid] = _open(self.file(rid), os.O_RDONLY)
            view = memoryview(out[rid])
            jobs += [(fds[rid], view[o:o + CHUNK], o) for o in range(0, size, CHUNK)]
        try:
            list(self._pool.map(lambda j: os.preadv(j[0], [j[1]], j[2]), jobs))
        finally:
            for fd in fds.values():
                os.close(fd)
        return out

    def disk_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.path.glob("room-*.notes"))

    def save(self) -> None:
        index = {"token_bytes": self.token_bytes, "room_tokens": self.room_tokens, "join": self.join,
                 "moments": [asdict(m) for m in self.moments], "rooms": [asdict(r) for r in self.rooms]}
        (self.path / "index.json").write_text(json.dumps(index))
        np.save(self.path / "vectors.npy", self.vectors)

    def close(self) -> None:
        self._pool.shutdown()
