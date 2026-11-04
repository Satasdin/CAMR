"""MATH-500 (Lightman et al., 2023): 500 competition problems from MATH, with their worked solutions.

The reply's last \\boxed{} answer is checked against the right one by value (see camr_engine.bench.suites.mathcheck).
"""

from __future__ import annotations

import json
from typing import Any

from camr_engine.bench.suites import mathcheck
from camr_engine.bench.suites.common import Item, clean, estimate_tokens, hub_file, rng, verdict

NAME = "math500"
REPO = "HuggingFaceH4/MATH-500"
REVISION = "6e4ed1a2a79af7d8630a6b768ec859cb5af4d3be"
INSTRUCTION = "Solve the problem. Put your final answer in \\boxed{}."


def _item(r: dict) -> Item:
    return Item(id=f"math500/{r['unique_id'].removeprefix('test/').removesuffix('.json')}", suite=NAME, context="",
                question=r["problem"], answer=r["answer"], length_tokens=estimate_tokens(r["problem"]),
                meta={"subject": r["subject"], "level": r["level"], "solution": r["solution"],
                      "instruction": INSTRUCTION})


def load(*, path: Any = None) -> list[Item]:
    """All 500 problems."""
    p = path or hub_file(REPO, "test.jsonl", REVISION, "math500")
    return [_item(json.loads(line)) for line in open(p) if line.strip()]


def sample(n: int, seed: int = 0, *, path: Any = None) -> list[Item]:
    """``n`` problems chosen by the seed, in the dataset's order."""
    items = load(path=path)
    picks = sorted(rng(seed, NAME).sample(range(len(items)), min(n, len(items))))
    return [items[k] for k in picks]


def prompt(item: Item) -> str:
    return f"{item.meta['instruction']}\n\n{item.question}"


def grade(item: Item, reply: str, **_: Any) -> str:
    ok, _ans = mathcheck.check(reply, str(item.answer))
    return verdict(ok, clean(reply))
