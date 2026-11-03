"""HARP (Yue et al., 2024): 4,780 short-answer problems from US maths contests, by subject and level 1-6, each with
one or more human worked solutions.

Here they become correction pairs. Problem A and its first worked solution are "the correction", fed in as context;
then problem B, never seen, of the same subject and level, is asked. A runner can also ask A first (``meta["first"]``)
so the correction follows the model's own attempt. Answers are checked by value (engram.bench.suites.mathcheck),
in the order HARP's own checker uses; its code is not run here, because it hands the reply to sympy's ``parse_expr``.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from engram.bench.suites import mathcheck
from engram.bench.suites.common import Item, clean, data_dir, estimate_tokens, rng, verdict

NAME = "harp"
COMMIT = "dac2734ff6443bcaf3bbdcb10f13cf21ae9729c2"
URL = f"https://github.com/aadityasingh/HARP/raw/{COMMIT}/HARP.jsonl.zip"
INSTRUCTION = "Solve the problem. Put your final answer in \\boxed{}."


def zip_path() -> Path:
    """The dataset's zip, downloaded once into ``data_dir("harp")``."""
    path = data_dir("harp") / "HARP.jsonl.zip"
    if not path.exists():
        from huggingface_hub.utils import get_session

        r = get_session().get(URL, follow_redirects=True, timeout=300)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def problems(path: Any = None) -> list[dict]:
    """Every short-answer problem with an answer and a worked solution, by id."""
    with zipfile.ZipFile(path or zip_path()) as z:
        name = next(n for n in z.namelist() if n.endswith(".jsonl") and not n.startswith("__MACOSX"))
        lines = io.TextIOWrapper(z.open(name), encoding="utf-8")
        rows = [json.loads(line) for line in lines if line.strip()]
    out = []
    for r in rows:
        if r.get("multiple_choice_only") or not str(r.get("answer", "")).strip() or not r.get("solution_1"):
            continue
        out.append({**r, "id": f"{r['year']}/{r['contest']}/{r['number']}"})
    return sorted(out, key=lambda r: r["id"])


def correction(a: dict) -> str:
    return f"Problem: {a['problem']}\n\nWorked solution: {a['solution_1']}\n\nFinal answer: {a['answer']}"


def pair(a: dict, b: dict) -> Item:
    """Problem B asked after A's correction."""
    ctx = correction(a)
    return Item(id=f"harp/{a['id']}->{b['id']}", suite=NAME, context=[ctx], question=b["problem"], answer=b["answer"],
                length_tokens=estimate_tokens(ctx),
                meta={"subject": b["subject"], "level": b["level"], "instruction": INSTRUCTION, "b_id": b["id"],
                      "first": {"id": a["id"], "problem": a["problem"], "answer": a["answer"]}})


def _groups(rows: list[dict], subject: str | None, level: int | None) -> dict[tuple[str, int], list[dict]]:
    g: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        if (subject is None or r["subject"] == subject) and (level is None or r["level"] == level):
            g[(r["subject"], r["level"])].append(r)
    return dict(sorted(g.items()))


def load(subject: str | None = None, level: int | None = None, *, path: Any = None) -> list[Item]:
    """Every problem in one pair: each subject and level shuffled once (seed 0), then taken two at a time."""
    out = []
    for key, rows in _groups(problems(path), subject, level).items():
        rows = list(rows)
        rng(0, NAME, *key).shuffle(rows)
        out += [pair(rows[k], rows[k + 1]) for k in range(0, len(rows) - 1, 2)]
    return out


def sample(n: int, seed: int = 0, subject: str | None = None, level: int | None = None, *,
           path: Any = None) -> list[Item]:
    """``n`` pairs chosen by the seed; no problem is used twice. B is drawn from every problem that matches, so
    subjects and levels come up as often as the dataset holds them."""
    groups = _groups(problems(path), subject, level)
    pool = [r for rows in groups.values() for r in rows]
    r = rng(seed, NAME, subject, level)
    order = r.sample(pool, len(pool))
    used: set[str] = set()
    out = []
    for b in order:
        if len(out) >= n:
            break
        if b["id"] in used:
            continue
        mates = [a for a in groups[(b["subject"], b["level"])] if a["id"] not in used and a["id"] != b["id"]]
        if not mates:
            continue
        a = r.choice(mates)
        used |= {a["id"], b["id"]}
        out.append(pair(a, b))
    return out


def prompt(item: Item, first: bool = False) -> str:
    """Problem B, or with ``first`` problem A (to ask before its correction)."""
    q = item.meta["first"]["problem"] if first else item.question
    return f"{item.meta['instruction']}\n\n{q}"


def grade(item: Item, reply: str, **_: Any) -> str:
    ok, _ans = mathcheck.check(reply, str(item.answer))
    return verdict(ok, clean(reply))


def grade_first(item: Item, reply: str) -> str:
    """The verdict on an attempt at problem A, before its correction."""
    ok, _ans = mathcheck.check(reply, str(item.meta["first"]["answer"]))
    return verdict(ok, clean(reply))
