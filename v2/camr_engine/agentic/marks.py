"""The memory gutter: a mark beside each line of code the agent wrote while leaning on memory, and beside each line a
person changed in the agent's code (design/DIRECTION.md, Code).

- ``used`` (green): some word written on the line looked at a moment on the desk with at least 0.10 of its
  attention (``events.USED``). The step's answer event gives, for each written word, the moment it looked at
  hardest; the words are joined back onto the lines of the file by finding each line in the reply.
- ``fix`` (violet): the same, where that moment is a saved fix, read back from the vault.
- ``yours`` (a violet tick, ``your fix · kept``): a line a person changed after the agent wrote the file. The change
  is told to the workspace's next run and, with memory on, kept in the project's memory as a "Your fix" moment
  (camr_engine.agentic.desk), so later answers can lean on it; a line written leaning on that moment is ``fix``.

Each ``used`` or ``fix`` mark keeps its step's path strip (``strip``), for the gutter's hover.

Marks are kept per workspace in one JSON file, with the text they belong to. When the file changes, marks on lines
that did not change follow them to their new line numbers, and the rest are dropped.
"""

from __future__ import annotations

import bisect
import difflib
import json
import os
import threading
from pathlib import Path

USED = 0.10
KEEP_TEXT = 1_000_000  # a file larger than this keeps no marks


def _lines(text: str) -> list[str]:
    return text.splitlines()


def leaning(text: str, pieces: list[str], memory: dict | None, start: int, end: int, content: str, form: str
            ) -> dict[int, dict]:
    """The lines of ``content`` (1-based) written while leaning on memory, found in the reply ``text`` between
    ``start`` and ``end`` (the tool call that wrote them). ``form`` is how the call wrote its arguments: ``json``
    (so each line is found escaped) or ``xml`` (as it is)."""
    if not memory or not memory.get("lean") or not pieces:
        return {}
    lean = memory["lean"]
    fixes = set(memory.get("fixes") or [])
    starts, at = [], 0
    for p in pieces:
        starts.append(at)
        at += len(p)
    out: dict[int, dict] = {}
    cursor = start
    for n, line in enumerate(_lines(content), 1):
        if not line.strip():
            continue
        needle = json.dumps(line)[1:-1] if form == "json" else line
        pos = text.find(needle, cursor, end)
        if pos < 0 and form == "json":
            needle = line
            pos = text.find(needle, cursor, end)
        if pos < 0:
            continue
        cursor = pos + len(needle)
        first = max(0, bisect.bisect_right(starts, pos) - 1)
        last = max(0, bisect.bisect_right(starts, pos + len(needle) - 1) - 1)
        best = None
        for i in range(first, min(last, len(lean) - 1) + 1):
            node, look = lean[i]
            if node is not None and look >= USED and (best is None or look > best[1]):
                best = (node, look)
        if best is not None:
            out[n] = {"kind": "fix" if best[0] in fixes else "used", "node": best[0], "look": best[1],
                      "reach": memory.get("reach"), "room": memory.get("room")}
    return out


def carry(before: str, after: str, marks: dict[int, dict]) -> dict[int, dict]:
    """Marks on ``before``'s lines moved to the same lines in ``after``; lines that changed lose theirs."""
    if not marks:
        return {}
    out = {}
    sm = difflib.SequenceMatcher(None, _lines(before), _lines(after), autojunk=False)
    for tag, i1, i2, j1, _ in sm.get_opcodes():
        if tag != "equal":
            continue
        for k in range(i2 - i1):
            m = marks.get(i1 + k + 1)
            if m is not None:
                out[j1 + k + 1] = m
    return out


def changed(before: str, after: str) -> tuple[list[int], list[tuple[str, str]]]:
    """The lines of ``after`` (1-based) that differ from ``before``, and each change as (old lines, new lines)."""
    a, b = _lines(before), _lines(after)
    lines, pairs = [], []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        lines.extend(range(j1 + 1, j2 + 1))
        pairs.append(("\n".join(a[i1:i2]), "\n".join(b[j1:j2])))
    return lines, pairs


class Marks:
    """One workspace's marks: ``{path: {"text": the file as marked, "lines": {line: mark}}}``."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        try:
            self.data: dict[str, dict] = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data))
        os.replace(tmp, self.path)

    def _get(self, rel: str) -> tuple[str, dict[int, dict]] | None:
        got = self.data.get(rel)
        if not got:
            return None
        return got["text"], {int(k): v for k, v in got["lines"].items()}

    def _put(self, rel: str, text: str, lines: dict[int, dict]) -> None:
        if len(text) > KEEP_TEXT:
            self.data.pop(rel, None)
        else:
            self.data[rel] = {"text": text, "lines": {str(k): v for k, v in sorted(lines.items())}}

    def wrote(self, rel: str, before: str | None, after: str, new: dict[int, dict], offset: int = 0) -> dict:
        """The agent wrote ``after``: earlier marks follow the unchanged lines, and ``new`` (lines of the written
        part, which starts ``offset`` lines into the file) goes on top. Returns the file's marks now."""
        with self.lock:
            old = self._get(rel)
            lines = carry(old[0], after, old[1]) if old is not None else {}
            for n, m in new.items():
                lines[n + offset] = m
            self._put(rel, after, lines)
            self._save()
            return {"text": after, "lines": lines}

    def saved(self, rel: str, before: str, after: str) -> tuple[dict, list[tuple[str, str]]]:
        """A person saved ``after`` over ``before``. For a file the agent wrote, the changed lines get a ``yours``
        mark; returns the marks now and the changes (empty for a file the agent never wrote)."""
        with self.lock:
            old = self._get(rel)
            if old is None:
                return {"text": after, "lines": {}}, []
            base = old[0] if old[0] == before else before
            lines = carry(old[0], after, old[1])
            nums, pairs = changed(base, after)
            for n in nums:
                lines[n] = {"kind": "yours"}
            self._put(rel, after, lines)
            self._save()
            return {"text": after, "lines": lines}, pairs

    def get(self, rel: str, now: str) -> dict[int, dict]:
        """The file's marks, moved onto its text now (it may have changed outside the app)."""
        with self.lock:
            old = self._get(rel)
        if old is None:
            return {}
        return old[1] if old[0] == now else carry(old[0], now, old[1])

    def moved(self, rel: str, to: str | None) -> None:
        with self.lock:
            got = self.data.pop(rel, None)
            if got is not None and to is not None:
                self.data[to] = got
            self._save()
