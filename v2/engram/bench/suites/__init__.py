"""Hugging Face suites: loaders, seeded samplers and graders, so a runner can ``load`` or ``sample`` items, feed each
item's context (or its chunks, in order), ask its question, and ``grade`` the reply.

  babilong          RMT-team/babilong qa1-qa5 at 4k to 1M tokens; the dataset's own answer rule
  memoryagentbench  ai-hyz/MemoryAgentBench, Conflict_Resolution and Accurate_Retrieval; exact match, in chunks
  math500           HuggingFaceH4/MATH-500; the \\boxed{} answer checked by value with sympy
  aime              MathArena/aime_2025 and aime_2026; a whole number 0-999, exact
  harp              aadityasingh/HARP as correction pairs: A's worked solution, then a new B of the same kind
  longmemeval       xiaowu0162/longmemeval-cleaned, S set; a judge model (``longmemeval.judge_prompt``)
  webdev            lmarena-ai/leaderboard-dataset webdev: rating history as a CSV and a summary (not items)

Every item has ``id``, ``suite``, ``context``, ``question``, ``answer``, ``length_tokens`` and ``meta``. ``grade``
gives a verdict: right, wrong or declined; for questions about things never said, right_abstain or false_memory.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, Callable

from engram.bench.suites import aime, babilong, harp, longmemeval, math500, memoryagentbench, webdev
from engram.bench.suites.common import RIGHT, Item, chunk, estimate_tokens

SUITES: dict[str, ModuleType] = {m.NAME: m for m in (babilong, memoryagentbench, math500, aime, harp, longmemeval)}
ALIASES = {"mab": "memoryagentbench", "math": "math500", "lme": "longmemeval", "lmarena": "webdev"}
HISTORIES: dict[str, ModuleType] = {webdev.NAME: webdev}

__all__ = ["Item", "RIGHT", "SUITES", "HISTORIES", "chunk", "estimate_tokens", "grade", "load", "module", "prompt",
           "sample"]


def module(name: str) -> ModuleType:
    """The suite's module, by name or alias."""
    key = ALIASES.get(name, name)
    if key in SUITES:
        return SUITES[key]
    raise KeyError(f"no suite {name!r}; there are {', '.join(SUITES)}")


def load(suite: str, **kw: Any) -> list[Item]:
    """Every item of a suite (see each module's ``load`` for its options)."""
    return module(suite).load(**kw)


def sample(suite: str, n: int, seed: int = 0, **kw: Any) -> list[Item]:
    """``n`` items per group the suite samples by (task and length, context, question kind, year), seeded."""
    return module(suite).sample(n, seed, **kw)


def prompt(item: Item) -> str:
    """The question as its suite asks it."""
    return module(item.suite).prompt(item)


def grade(item: Item, reply: str, judge: Callable[[str], str] | None = None) -> str:
    """The verdict on ``reply``. ``judge`` (prompt -> reply text) is only used by suites that need one."""
    return module(item.suite).grade(item, reply, judge=judge)
