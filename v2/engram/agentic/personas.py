"""Personas: a system prompt with a name, the memory reaches it reads and the one it writes, and the tools it may use.
Choosing a persona on the Code screen sets the reach (design/DIRECTION.md, Code). Three come built in; a person can
change them or add their own, which are saved in ``personas.json``. Changing a built-in one saves a copy under the
same id, and deleting that copy brings the built-in back.
"""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engram.reach import KINDS

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
SYSTEM_LIMIT = 8000
READ_ONLY = ["read_file", "list_files", "search", "load_skill"]


@dataclass
class Persona:
    id: str
    name: str
    system: str
    reads: list[str] = field(default_factory=lambda: ["session", "project", "global"])
    writes: str = "project"
    tools: list[str] | None = None  # None: every tool; otherwise only these (MCP tools by their full name)
    built_in: bool = False

    def allows(self, tool: str) -> bool:
        return self.tools is None or tool in self.tools or (tool.startswith("mcp__") and "mcp" in self.tools)

    def show(self) -> dict:
        return asdict(self)


BUILT_IN = [
    Persona("coder", "Coder", "You are a careful software engineer working in the user's project. Read the files a "
            "change touches before you change them, keep each change small, and follow the code's own names and "
            "style. Use what you remember about this project: its helpers, its rules and the user's earlier fixes.",
            built_in=True),
    Persona("reviewer", "Reviewer", "You review code in the user's project. Read the files you are asked about and "
            "report problems: bugs first, then unclear names, then missing tests. You do not change files.",
            reads=["project", "global"], writes="session", tools=READ_ONLY, built_in=True),
    Persona("tester", "Tester", "You write and run tests for the user's project. Find how the project runs its "
            "tests, add tests for the behaviour you are asked about, run them, and report what passed and what "
            "failed.", built_in=True),
]


def check(raw: dict) -> Persona:
    """A persona from the page, checked: ValueError says what is wrong."""
    pid = str(raw.get("id") or "").strip().lower()
    if not _ID.match(pid):
        raise ValueError("a persona's id is lowercase letters, digits and -, at most 32")
    name = " ".join(str(raw.get("name") or "").split())[:40]
    if not name:
        raise ValueError("give the persona a name")
    system = str(raw.get("system") or "").strip()
    if not system or len(system) > SYSTEM_LIMIT:
        raise ValueError(f"the system prompt is 1 to {SYSTEM_LIMIT} characters")
    reads = [str(r) for r in raw.get("reads") or []]
    if not reads or any(r not in KINDS for r in reads):
        raise ValueError(f"a persona reads one or more of {', '.join(KINDS)}")
    writes = str(raw.get("writes") or reads[0])
    if writes not in KINDS:
        raise ValueError(f"a persona writes to one of {', '.join(KINDS)}")
    if writes not in reads:
        reads = [writes, *reads]
    tools = raw.get("tools")
    if tools is not None:
        if not isinstance(tools, list) or not all(isinstance(t, str) and len(t) <= 96 for t in tools):
            raise ValueError("tools is a list of tool names, or left out for every tool")
        tools = list(dict.fromkeys(tools))[:64]
    return Persona(pid, name, system, list(dict.fromkeys(reads)), writes, tools,
                   built_in=any(p.id == pid for p in BUILT_IN))


class Personas:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def _saved(self) -> dict[str, Persona]:
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        out = {}
        for x in raw.get("personas", []) if isinstance(raw, dict) else []:
            try:
                p = check(x)
            except (ValueError, AttributeError, TypeError):
                continue
            out[p.id] = p
        return out

    def _write(self, saved: dict[str, Persona]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"personas": [asdict(p) for p in saved.values()]}, indent=1))
        os.replace(tmp, self.path)

    def all(self) -> list[Persona]:
        with self.lock:
            saved = self._saved()
        out = [saved.pop(p.id, p) for p in BUILT_IN]
        return out + sorted(saved.values(), key=lambda p: p.name.lower())

    def get(self, pid: str) -> Persona:
        for p in self.all():
            if p.id == pid:
                return p
        raise KeyError(pid)

    def save(self, raw: dict) -> Persona:
        p = check(raw)
        with self.lock:
            saved = self._saved()
            if p.id not in saved and len(saved) >= 64:
                raise ValueError("at most 64 saved personas")
            saved[p.id] = p
            self._write(saved)
        return p

    def delete(self, pid: str) -> None:
        """Delete a saved persona (for a built-in one, its changed copy)."""
        with self.lock:
            saved = self._saved()
            if pid not in saved:
                raise KeyError(pid)
            del saved[pid]
            self._write(saved)
