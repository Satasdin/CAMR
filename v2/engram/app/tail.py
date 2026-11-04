"""Reading a growing JSON-lines log from line N on, without reading the whole file each time.

The page polls ``events.jsonl`` and ``metrics.jsonl`` once a second. A Tail remembers where each line starts, so a
poll reads only the lines it returns and the bytes added since the last poll. Lines are counted as
``EventLog.read`` counts them (blank lines skipped), so a line's number is the event id the rest of the app uses. A
file that shrank (a new memory in the same place) is read again from the start.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

LIMIT = 500


class Tail:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.starts: list[int] = []  # byte offset of each non-blank line
        self.scanned = 0  # bytes scanned so far
        self.lock = threading.Lock()

    def _scan(self) -> None:
        try:
            size = self.path.stat().st_size
        except OSError:
            self.starts, self.scanned = [], 0
            return
        if size < self.scanned:
            self.starts, self.scanned = [], 0
        if size == self.scanned:
            return
        with self.path.open("rb") as f:
            f.seek(self.scanned)
            data = f.read(size - self.scanned)
        end = data.rfind(b"\n") + 1  # a line still being written waits for its newline
        pos = 0
        while pos < end:
            nl = data.index(b"\n", pos)
            if data[pos:nl].strip():
                self.starts.append(self.scanned + pos)
            pos = nl + 1
        self.scanned += end

    def read(self, after: int | None = None, *, limit: int = LIMIT, tail: int = 0) -> dict:
        """Lines ``after`` on (at most ``limit``), each with its number as ``i``; with ``after`` None, the last
        ``tail`` lines. ``next`` is the number to ask after next time."""
        limit = max(0, min(limit, LIMIT))
        with self.lock:
            self._scan()
            total = len(self.starts)
            start = max(0, total - min(tail, LIMIT)) if after is None else max(0, min(after, total))
            stop = min(total, start + limit)
            out = []
            if stop > start:
                with self.path.open("rb") as f:
                    f.seek(self.starts[start])
                    end = self.starts[stop] if stop < total else self.scanned
                    chunk = f.read(end - self.starts[start])
                lines = [ln for ln in chunk.split(b"\n") if ln.strip()]
                for i, line in zip(range(start, stop), lines):
                    try:
                        item = json.loads(line)
                    except ValueError:
                        item = {"type": "unreadable"}
                    if isinstance(item, dict):
                        item["i"] = i
                        out.append(item)
            return {"next": stop, "total": total, "events": out}
