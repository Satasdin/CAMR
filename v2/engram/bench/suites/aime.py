"""AIME 2025 and 2026 (from MathArena): 30 problems a year, each answer a whole number from 0 to 999.

The reply's final answer (its last \\boxed{}, else "the answer is ...", else a short reply) must be that number.
"""

from __future__ import annotations

import re
from typing import Any

from engram.bench.suites import mathcheck
from engram.bench.suites.common import Item, clean, estimate_tokens, hub_file, rng, verdict

NAME = "aime"
YEARS = (2025, 2026)
REVISIONS = {2025: "c94da77eb22bbd6439e62a323bec18493a421302", 2026: "d61f486805306e6e6b5913504c07763a99e1b112"}
FILE = "data/train-00000-of-00001.parquet"
INSTRUCTION = "Solve the problem. The answer is a whole number from 0 to 999. Put it in \\boxed{}."


def _rows(year: int, path: Any = None) -> list[dict]:
    import pyarrow.parquet as pq

    p = path or hub_file(f"MathArena/aime_{year}", FILE, REVISIONS[year], f"aime/{year}")
    return pq.read_table(p).to_pylist()


def load(years: tuple[int, ...] = YEARS, *, paths: dict[int, Any] | None = None) -> list[Item]:
    """Every problem of these years."""
    out = []
    for y in years:
        for r in _rows(y, (paths or {}).get(y)):
            out.append(Item(id=f"aime/{y}/{int(r['problem_idx']):02d}", suite=NAME, context="",
                            question=r["problem"], answer=str(int(r["answer"])),
                            length_tokens=estimate_tokens(r["problem"]),
                            meta={"year": y, "number": int(r["problem_idx"]), "kind": r.get("problem_type") or [],
                                  "instruction": INSTRUCTION}))
    return out


def sample(n: int, seed: int = 0, years: tuple[int, ...] = YEARS, *, paths: dict[int, Any] | None = None) -> list[Item]:
    """``n`` problems a year, chosen by the seed."""
    out = []
    for y in years:
        items = load((y,), paths=paths)
        out += [items[k] for k in sorted(rng(seed, NAME, y).sample(range(len(items)), min(n, len(items))))]
    return out


def prompt(item: Item) -> str:
    return f"{item.meta['instruction']}\n\n{item.question}"


def integer(answer: str | None) -> int | None:
    """"070", "70.", "$70$", "\\text{70}", "1,000" -> the number; anything else -> None."""
    if answer is None:
        return None
    t = mathcheck.as_text(answer).replace(",", "")
    m = re.fullmatch(r"([+-]?)0*(\d+)(?:\.0*)?", t)
    return int(m.group(1) + m.group(2)) if m else None


def grade(item: Item, reply: str, **_: Any) -> str:
    got = integer(mathcheck.extract(reply))
    return verdict(got is not None and got == int(item.answer), clean(reply))
