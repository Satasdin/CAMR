"""The core: the subconscious, a small always-on block of notes (persona, standing facts) kept in RAM.

It is built from the vault's notes tagged ``core``, read once by the model as notes (its keys and values, with the
same Notebook that writes rooms) and kept in RAM. It goes on every desk right after the header and before the room,
so it is attended on every answer without being read again. Rooms were written straight after the header, so on a
desk with the core their keys are turned along by the core's length (see engram.notes).

The core stays small, about 256 tokens: pinned notes go in first, then the strongest, and whatever does not fit is
left out and listed. When the chosen notes or their words change, the core is written again. Before each answer the
vaults are looked at again (cheaply: see Vault.rescan), so a core note edited in Obsidian, a new note tagged core,
or a deleted one changes the core on the next answer without reopening anything.
"""

from __future__ import annotations

from typing import Callable, Iterable

from engram.vault import CORE, Note, Vault

CORE_TOKENS = 256


class Core:
    """The core block for the vaults given (one, or every vault a session reads)."""

    def __init__(self, notebook, ids: Callable[[str], list[int]], vaults: Iterable[Vault], *,
                 budget: int = CORE_TOKENS, tag: str = CORE):
        self.notebook, self._ids, self.vaults, self.budget, self.tag = notebook, ids, list(vaults), budget, tag
        self.notes = None  # (tokens, layers, 2, kv_heads, head_dim), in RAM; None while the core is empty
        self.members: list[str] = []  # the notes in it, in the order they are read
        self.left_out: list[str] = []  # core notes that did not fit the budget
        self.tokens = 0
        self.writes = 0  # how many times it has been written
        self._key: tuple = ()
        self._seen: tuple = ()
        self._words: dict[tuple, tuple[str, list[int]]] = {}  # (vault, id, digest) -> (words, token ids)
        self._texts: list[str] = []

    @property
    def bytes(self) -> int:
        return self.tokens * self.notebook.shape.token_bytes if self.notes is not None else 0

    def candidates(self) -> list[tuple[int, Note]]:
        """Every core-tagged note as (which vault, note), most deserving first: pinned, then strongest, then oldest."""
        notes = [(i, n) for i, v in enumerate(self.vaults) for n in v.notes(tag=self.tag)]
        return sorted(notes, key=lambda vn: (not vn[1].pinned, -vn[1].strength,
                                             vn[1].day if vn[1].day is not None else -1, vn[0], vn[1].id))

    def refresh(self) -> bool:
        """Write the core again if its notes changed (by the engine or by hand). Returns True when it was written."""
        for v in self.vaults:
            v.rescan(tag=self.tag)
        seen = tuple(v.version for v in self.vaults)
        if seen == self._seen:
            return False
        self._seen = seen
        chosen, left, total, words = [], [], 0, {}
        for i, n in self.candidates():
            k = (i, n.id, n.digest)
            got = self._words.get(k) or self._read(i, n.id)
            if got is None:  # its file was deleted
                continue
            words[k] = got
            size = len(words[k][1])
            if total + size > self.budget:
                left.append(n.id)
                continue
            chosen.append((i, n))
            total += size
        self._words = words  # only the words of notes still tagged core
        chosen.sort(key=lambda vn: (vn[1].day if vn[1].day is not None else -1, vn[0], vn[1].id))  # date order
        key = tuple((i, n.id, n.digest) for i, n in chosen)
        self.left_out = left
        if key == self._key:
            return False
        ids = [t for k in key for t in words[k][1]]
        self.notes = self.notebook.write(ids) if ids else None
        self.members, self.tokens, self._key = [n.id for _, n in chosen], len(ids), key
        self._texts = [words[k][0] for k in key]
        self.writes += 1
        return True

    def text(self) -> str:
        """The core as a person would read it."""
        return "\n".join(self._texts)

    def _read(self, vault: int, nid: str) -> tuple[str, list[int]] | None:
        note = self.vaults[vault].read(nid)
        if note is None:
            return None
        text = note.text or ""
        return text, self._ids(text)
