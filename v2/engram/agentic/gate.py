"""The gate: a shell command or an MCP call the model asks for waits here until the person allows or denies it in the
page. Each ask is one exact action (the command as it will run, or the server, tool and arguments), with an id made
for it; allowing it runs that action once and nothing else. An ask nobody answers is denied after a while, and
stopping a run denies what it was waiting for. There is no "allow everything" switch.
"""

from __future__ import annotations

import copy
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field

WAIT_S = 600.0  # an ask nobody answers is denied after ten minutes


@dataclass
class Ask:
    id: str
    kind: str  # "shell" or "mcp"
    what: dict  # exactly what will run: {"command", "cwd"} or {"server", "tool", "arguments"}
    owner: str  # the run (or swarm agent) that asked
    label: str = ""  # who asked, for the page: "A3", or the thread's title
    at: float = field(default_factory=time.time)
    decision: str | None = None  # "allowed", "denied", "timed out" or "stopped"
    decided_at: float | None = None
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def allowed(self) -> bool:
        return self.decision == "allowed"

    def show(self) -> dict:
        return {"id": self.id, "kind": self.kind, "what": self.what, "owner": self.owner, "label": self.label,
                "at": self.at, "decision": self.decision, "decided_at": self.decided_at}


class Gate:
    def __init__(self, wait_s: float = WAIT_S):
        self.wait_s = wait_s
        self.lock = threading.Lock()
        self.pending: dict[str, Ask] = {}
        self.decided: deque[Ask] = deque(maxlen=200)

    def ask(self, kind: str, what: dict, *, owner: str, label: str = "", cancel: threading.Event | None = None,
            wait_s: float | None = None) -> Ask:
        """Wait for the person's answer to one action. Returns the Ask with its decision; run ``ask.what`` (a copy
        made here, so nothing changes after it was shown) only when ``ask.allowed``."""
        a = Ask(secrets.token_urlsafe(12), kind, copy.deepcopy(what), owner, label)
        with self.lock:
            self.pending[a.id] = a
        limit = time.monotonic() + (self.wait_s if wait_s is None else wait_s)
        while not a._done.is_set():
            if cancel is not None and cancel.is_set():
                self._settle(a, "stopped")
                break
            left = limit - time.monotonic()
            if left <= 0:
                self._settle(a, "timed out")
                break
            a._done.wait(min(left, 0.1))
        return a

    def decide(self, ask_id: str, allow: bool) -> Ask:
        """The person's answer. KeyError for an ask that is not waiting (unknown, or answered already)."""
        with self.lock:
            a = self.pending.get(ask_id)
            if a is None:
                raise KeyError(ask_id)
        self._settle(a, "allowed" if allow else "denied")
        return a

    def _settle(self, a: Ask, decision: str) -> None:
        with self.lock:
            if a.decision is not None:
                return
            a.decision, a.decided_at = decision, time.time()
            self.pending.pop(a.id, None)
            self.decided.append(a)
        a._done.set()

    def waiting(self, owner: str | None = None) -> list[dict]:
        with self.lock:
            return [a.show() for a in self.pending.values() if owner is None or a.owner == owner]

    def cancel(self, owner: str) -> int:
        """Deny everything ``owner`` is waiting for (its run stopped)."""
        with self.lock:
            mine = [a for a in self.pending.values() if a.owner == owner]
        for a in mine:
            self._settle(a, "stopped")
        return len(mine)
