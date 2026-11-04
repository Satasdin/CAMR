"""The tiers: where each room's notes are when a question needs them.

- **RAM** holds the core and the hot rooms: the most recently used rooms that fit the RAM budget, kept already
  turned into arrays the desk can take, so a hit skips the SSD and the copy. Several memories (a session's reaches)
  can share one RAM budget, the core counted once, through one Pool.
- **SSD** holds every awake room's file, read in one burst when the room is not hot.
- **Vault** holds the words of every moment. When the room files outgrow the disk budget, the weakest and least
  recently used rooms go to sleep: their ``.notes`` file is deleted, and their moments stay in the index and the
  vault as words. A question whose room is asleep reads that room's moments as words, or wakes the room (its notes
  written again from its words) when ``wake`` is on.

Every read reports the tier it hit, the bytes it read from the SSD and how long that took, so each recall can give
its retrieval time and bandwidth.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass
from typing import Callable, Iterable

from camr_engine.rooms import Rooms, _open

RAM, SSD, VAULT = "ram", "ssd", "vault"
RAM_BYTES = 512 * 2**20  # the hot rooms and the core together; about nine full rooms of the 1.7B's notes
STATE = "tiers.json"


@dataclass
class Read:
    """One room's notes, fetched for the desk."""

    tier: str  # where they were: RAM, SSD, or VAULT (asleep: only words, unless woken)
    data: object | None  # the notes as the desk takes them; None when the room is asleep and stays asleep
    bytes: int = 0  # read from the SSD
    seconds: float = 0.0  # the SSD read
    convert_s: float = 0.0  # turning the bytes into arrays
    woke: bool = False
    wake_s: float = 0.0  # writing the room's notes again from its words

    @property
    def gbps(self) -> float | None:
        return self.bytes / self.seconds / 1e9 if self.bytes and self.seconds > 0 else None


class Pool:
    """RAM for hot rooms: one budget for the core and every hot room in it, the least recently used room out first.
    Each Tiers has a pool of its own unless given one to share."""

    def __init__(self, ram_bytes: int = RAM_BYTES):
        self.budget = ram_bytes
        self._core = 0
        self.hot: OrderedDict[tuple, object] = OrderedDict()  # (tiers, room) -> notes, least recently used first
        self.sizes: dict[tuple, int] = {}

    @property
    def core_bytes(self) -> int:
        """The core's notes, which always stay in RAM."""
        return self._core

    @core_bytes.setter
    def core_bytes(self, n: int) -> None:
        self._core = n
        self.fit()

    def used_bytes(self) -> int:
        return self._core + sum(self.sizes.values())

    def get(self, key):
        """A hot room's notes (now the most recently used), or None."""
        if key not in self.hot:
            return None
        self.hot.move_to_end(key)
        return self.hot[key]

    def put(self, key, data, size: int) -> None:
        """Keep a room hot. A room bigger than all the room left beside the core is not kept, and pushes nothing
        out."""
        if size > self.budget - self._core:
            self.drop(key)
            return
        self.hot[key] = data
        self.sizes[key] = size
        self.hot.move_to_end(key)
        self.fit()

    def drop(self, key) -> None:
        self.hot.pop(key, None)
        self.sizes.pop(key, None)

    def fit(self) -> None:
        """Evict the least recently used hot rooms until RAM fits."""
        room_left = self.budget - self._core
        for key in [k for k, n in self.sizes.items() if n > room_left]:
            self.drop(key)
        while self.hot and sum(self.sizes.values()) > room_left:
            key, _ = self.hot.popitem(last=False)
            self.sizes.pop(key, None)


class Tiers:
    """RAM and disk budgets for one memory's rooms. Made with its budgets, then bound to the rooms (``bind``).
    ``pool`` is RAM shared with other memories' tiers; its budget is used instead of ``ram_bytes``."""

    def __init__(self, ram_bytes: int = RAM_BYTES, disk_bytes: int | None = None, *, wake: bool = False,
                 pool: Pool | None = None):
        self.pool = pool if pool is not None else Pool(ram_bytes)
        self.disk_budget, self.wake = disk_bytes, wake
        self.sleeping: set[int] = set()
        self.used: dict[int, int] = {}  # room -> the tick it was last read or written
        self.tick = 0
        self.hits: Counter = Counter()
        self.rooms: Rooms | None = None

    def bind(self, rooms: Rooms, *, convert: Callable = lambda buf, rid=None: buf, join: Callable | None = None,
             rewrite: Callable[[int], bytes] | None = None, strength: Callable[[int], float] | None = None,
             notify: Callable[[list[int], bool], None] | None = None) -> Tiers:
        """Attach to ``rooms``. ``convert(buf, rid)`` turns room ``rid``'s file into what the desk takes (its bytes
        are at that room's bits); ``join`` appends new notes
        to a hot room; ``rewrite`` writes a room's notes again from its words (for waking); ``strength`` says how
        strong a room is (default: all equal, so the least recently used sleep first); ``notify`` hears of rooms
        going to sleep (True) or waking (False)."""
        self.rooms, self._convert, self._join, self._rewrite = rooms, convert, join, rewrite
        self._strength, self._notify = strength or (lambda rid: 1.0), notify
        self.sleeping = {r.rid for r in rooms.rooms if r.tokens and not rooms.file(r.rid).exists()}
        state = rooms.path / STATE
        if state.exists():
            try:
                saved = json.loads(state.read_text())
                self.tick = int(saved.get("tick", 0))
                self.used = {int(k): int(v) for k, v in saved.get("used", {}).items()}
            except (ValueError, OSError):
                pass
        return self

    # -- RAM, through the pool

    @property
    def ram_budget(self) -> int:
        return self.pool.budget

    @property
    def core_bytes(self) -> int:
        return self.pool.core_bytes

    @core_bytes.setter
    def core_bytes(self, n: int) -> None:
        self.pool.core_bytes = n

    @property
    def hot(self) -> OrderedDict[int, object]:
        """This memory's hot rooms, least recently used first (a copy: change them through load, wrote, forget)."""
        return OrderedDict((rid, d) for (t, rid), d in self.pool.hot.items() if t is self)

    @property
    def sizes(self) -> dict[int, int]:
        return {rid: n for (t, rid), n in self.pool.sizes.items() if t is self}

    # -- reading

    def is_asleep(self, rid: int) -> bool:
        return rid in self.sleeping

    def touch(self, rid: int) -> None:
        self.tick += 1
        self.used[rid] = self.tick

    def load(self, rid: int) -> Read:
        """Room ``rid``'s notes from the fastest tier that has them. Waking a room writes its file back, so the disk
        budget is held again at once, the woken room kept awake."""
        self.touch(rid)
        data = self.pool.get((self, rid))
        if data is not None:
            self.hits[RAM] += 1
            return Read(RAM, data)
        if rid in self.sleeping:
            self.hits[VAULT] += 1
            if not (self.wake and self._rewrite):
                return Read(VAULT, None)
            t = time.perf_counter()
            buf = self.wake_room(rid)
            wake_s = time.perf_counter() - t
            t = time.perf_counter()
            data = self._convert(buf, rid)
            got = Read(VAULT, data, convert_s=time.perf_counter() - t, woke=True, wake_s=wake_s)
            self._keep(rid, data, _ram(data, buf))
            self.enforce(keep={rid})
            return got
        self.hits[SSD] += 1
        t = time.perf_counter()
        buf = self.rooms.fetch([rid])[rid]
        seconds = time.perf_counter() - t
        t = time.perf_counter()
        data = self._convert(buf, rid)
        got = Read(SSD, data, len(buf), seconds, time.perf_counter() - t)
        self._keep(rid, data, _ram(data, buf))
        return got

    # -- writing

    def wrote(self, rid: int, notes=None, size: int = 0) -> list[int]:
        """A moment's notes were appended to room ``rid``: keep a hot copy current, then hold the disk budget.
        Returns the rooms put to sleep."""
        self.touch(rid)
        key = (self, rid)
        if key in self.pool.hot:
            if self._join is not None and notes is not None:
                self.pool.put(key, self._join(self.pool.hot[key], notes), self.pool.sizes[key] + size)
            else:
                self.forget(rid)
        return self.enforce()

    def forget(self, rid: int) -> None:
        """Drop a room's hot copy (it stays on the SSD)."""
        self.pool.drop((self, rid))

    def enforce(self, keep: Iterable[int] = ()) -> list[int]:
        """Put rooms to sleep, weakest first and, among equally strong rooms, least recently used first, until the
        awake room files fit the disk budget. Rooms in ``keep`` stay awake."""
        if self.disk_budget is None or self.rooms is None:
            return []
        size = self.rooms.room_bytes
        awake = [r for r in self.rooms.rooms if r.tokens and r.rid not in self.sleeping]
        total = sum(size(r.rid) for r in awake)
        if total <= self.disk_budget:
            return []
        keep = set(keep)
        order = sorted((r for r in awake if r.rid not in keep),
                       key=lambda r: (round(self._strength(r.rid), 2), self.used.get(r.rid, 0), r.rid))
        slept = []
        for r in order:
            if total <= self.disk_budget:
                break
            self.sleep(r.rid, tell=False)
            total -= size(r.rid)
            slept.append(r.rid)
        if slept and self._notify:
            self._notify(slept, True)
        return slept

    def sleep(self, rid: int, *, tell: bool = True) -> None:
        """Delete room ``rid``'s notes file; its moments stay as words."""
        self.rooms.file(rid).unlink(missing_ok=True)
        self.forget(rid)
        self.sleeping.add(rid)
        if tell and self._notify:
            self._notify([rid], True)

    def wake_room(self, rid: int) -> bytes:
        """Write room ``rid``'s notes again from its words (at the room's bits), back onto the SSD. Returns them."""
        if self._rewrite is None:
            raise ValueError("these tiers cannot wake a room")
        data = self._rewrite(rid)
        if len(data) != self.rooms.room_bytes(rid):
            raise ValueError("a woken room must come back the size it was")
        fd = _open(self.rooms.file(rid), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        self.sleeping.discard(rid)
        if self._notify:
            self._notify([rid], False)
        return data

    # -- what is where

    def ram_bytes(self) -> int:
        """The core and every hot room in this memory's pool (shared with other memories when the pool is)."""
        return self.pool.used_bytes()

    def disk_bytes(self) -> int:
        """The awake rooms' files, as the index counts them."""
        if self.rooms is None:
            return 0
        return sum(self.rooms.room_bytes(r.rid) for r in self.rooms.rooms if r.rid not in self.sleeping)

    def state(self) -> dict:
        """What sits in each tier, for a person to look at."""
        n = len(self.rooms.rooms) if self.rooms else 0
        return {"ram": {"budget_bytes": self.ram_budget, "used_bytes": self.ram_bytes(), "core_bytes": self.core_bytes,
                        "rooms": list(self.hot)},
                "ssd": {"budget_bytes": self.disk_budget, "used_bytes": self.disk_bytes(),
                        "rooms": n - len(self.sleeping)},
                "vault": {"rooms": sorted(self.sleeping)},
                "hits": dict(self.hits)}

    def save(self) -> None:
        if self.rooms is None:
            return
        path = self.rooms.path / STATE
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"tick": self.tick, "used": self.used}))
        os.replace(tmp, path)

    # -- inside

    def _keep(self, rid: int, data, size: int) -> None:
        self.pool.put((self, rid), data, size)


def _ram(data, buf) -> int:
    """What a room's notes take in RAM once turned into arrays (more than its file when the file is quantized)."""
    return int(getattr(data, "nbytes", len(buf)))
