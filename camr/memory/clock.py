"""Clocks that drive the recency term (Equation 4.3).

The proposal notes (section 4.4.7) that batch ingestion gives every note a
near-identical creation time, so recency is driven by access *during a run*.
Using wall-clock time for that makes rankings depend on how fast the machine is,
which breaks the byte-identical-prompt requirement (NFR-05).  Experiments
therefore use a ``LogicalClock`` that advances a fixed step per question, so
"hours since last access" means "questions since last access" and two
executions of the same configuration see exactly the same recency values.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod

from camr.memory.note import utcnow


class Clock(ABC):
    @abstractmethod
    def now(self) -> dt.datetime: ...

    def tick(self) -> None:  # advanced by the harness once per question
        return None


class WallClock(Clock):
    def now(self) -> dt.datetime:
        return utcnow()


class LogicalClock(Clock):
    def __init__(self, start: dt.datetime, step_hours: float = 1.0):
        self._t = start
        self._step = dt.timedelta(hours=step_hours)

    def now(self) -> dt.datetime:
        return self._t

    def tick(self) -> None:
        self._t = self._t + self._step
