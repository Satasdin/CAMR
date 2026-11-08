"""Rooms: related moments kept side by side on the SSD, one file per room, fetched whole in one burst.

A room's file holds its moments' notes token by token (see camr_engine.notes), so a moment joins a room by appending to
the end of its file. What a person reads (each moment's words, its day, its embedding) stays in a small index beside
the files. Every read and write bypasses the Mac's file cache, so a fetch is a real SSD read, never a copy in RAM.

Each room keeps its notes at 16, 8 or 4 bits (camr_engine.notes.pack), said by the index and by the file's name:
``room-000001.notes`` at 16 bits, as every room was before quantized rooms existed; ``room-000001.q8.notes`` and
``room-000001.q4.notes`` quantized. New rooms take the memory's ``bits``; a room keeps the bits it was started with,
so rooms on the SSD from before still read, and a moment joining one is appended at that room's bits.
"""

from __future__ import annotations

import fcntl
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from camr_engine.notes import stored_bytes

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
    bits: int = 16  # how its notes are kept on the SSD (rooms saved before this was kept are all 16-bit)


def room_file(folder: Path, rid: int, bits: int = 16) -> Path:
    """Where room ``rid``'s notes are kept at ``bits``."""
    return Path(folder) / (f"room-{rid:06d}.notes" if bits == 16 else f"room-{rid:06d}.q{bits}.notes")


def kept_file(folder: Path, rid: int) -> Path:
    """Room ``rid``'s notes file as it is on the SSD, at whatever bits (the 16-bit name when there is none)."""
    for bits in (16, 8, 4):
        f = room_file(folder, rid, bits)
        if f.exists():
            return f
    return room_file(folder, rid)


def room_id(path: Path) -> int:
    """The room a notes file holds, from its name."""
    return int(Path(path).name.split("-")[1].split(".")[0])


def _open(path: Path, flags: int) -> int:
    fd = os.open(path, flags, 0o644)
    try:
        fcntl.fcntl(fd, F_NOCACHE, 1)
    except OSError:  # not macOS: plain reads and writes
        pass
    return fd


class Rooms:
    """The memory on the SSD. ``token_bytes`` is the size of one token's notes at 16 bits (the model's own); ``bits``
    is how a new room keeps them; ``room_tokens`` caps a room; a moment joins the room holding its closest moment when
    that closeness is at least ``join``, otherwise it starts a room."""

    def __init__(self, path: Path, token_bytes: int, room_tokens: int, join: float, *, bits: int = 16):
        stored_bytes(token_bytes, bits)  # checks bits
        self.path, self.token_bytes, self.room_tokens, self.join = Path(path), token_bytes, room_tokens, join
        self.bits = bits
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
                f, size = self.file(room.rid), self.room_bytes(room.rid)
                if f.exists() and f.stat().st_size > size:
                    os.truncate(f, size)

    def file(self, rid: int) -> Path:
        return room_file(self.path, rid, self.rooms[rid].bits if rid < len(self.rooms) else self.bits)

    def bits_of(self, rid: int | None) -> int:
        """The bits room ``rid`` keeps its notes at (a new room's when it is None)."""
        return self.bits if rid is None else self.rooms[rid].bits

    def token_size(self, rid: int | None) -> int:
        """One token's notes in room ``rid``'s file (in a new room's when it is None)."""
        return stored_bytes(self.token_bytes, self.bits_of(rid))

    def room_bytes(self, rid: int) -> int:
        """Room ``rid``'s file, as the index counts it."""
        return self.rooms[rid].tokens * self.token_size(rid)

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

    def add(self, text: str, day: int, vec: np.ndarray, notes: bytes | None, rid: int | None, *,
            tokens: int | None = None) -> Moment:
        """Append a moment's notes to room ``rid`` (from ``place``), or to a new room when it is None. ``notes`` are
        packed at that room's bits (``bits_of(rid)``). With ``notes`` None the moment joins as words only (``tokens``
        long): nothing is written, and the room's file, if it ever has one, is written whole when it wakes."""
        if notes is None:
            if tokens is None:
                raise ValueError("a moment kept as words says how many tokens it is")
        else:
            tokens = len(notes) // self.token_size(rid)
        if rid is None:
            rid = len(self.rooms)
            self.rooms.append(Room(rid, bits=self.bits))
        room = self.rooms[rid]
        if notes is not None:
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
            size = self.room_bytes(rid)
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
        index = {"token_bytes": self.token_bytes, "bits": self.bits, "room_tokens": self.room_tokens, "join": self.join,
                 "moments": [asdict(m) for m in self.moments], "rooms": [asdict(r) for r in self.rooms]}
        tmp = self.path / "index.json.tmp"
        tmp.write_text(json.dumps(index))
        os.replace(tmp, self.path / "index.json")
        np.save(self.path / "vectors.npy", self.vectors)

    def close(self) -> None:
        self._pool.shutdown()
