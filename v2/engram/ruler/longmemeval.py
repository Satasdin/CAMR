"""LongMemEval (Wu et al., 2024): 500 questions, each over its own history of chat sessions.

The files the old CAMR downloaded live in ``~/.cache/camr-bench/longmemeval/``: ``oracle`` (only the sessions that
hold the answer), ``s`` (about 50 sessions per question) and ``m`` (about 500). Each question becomes an ``Item``
whose sessions are dated days of notes, in the same "[YYYY-MM-DD] ..." form as the scripted lives.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home() / ".cache" / "camr-bench" / "longmemeval"
FILES = {"oracle": "longmemeval_oracle.json", "s": "longmemeval_s_cleaned.json", "m": "longmemeval_m_cleaned.json"}


def parse_date(text: str) -> dt.date:
    """'2023/04/10 (Mon) 17:50' -> 2023-04-10."""
    return dt.datetime.strptime(text.split(" ")[0], "%Y/%m/%d").date()


@dataclass
class Item:
    qid: str
    kind: str  # LongMemEval's question type; ids ending "_abs" are questions that should be declined
    question: str
    answer: str
    asked: dt.date
    sessions: list[tuple[dt.date, list[str]]]  # oldest first; one note per turn

    @property
    def should_decline(self) -> bool:
        return self.qid.endswith("_abs")


def load(variant: str = "oracle", path: Path | None = None, limit: int | None = None) -> list[Item]:
    raw = json.loads((path or HOME / FILES[variant]).read_text())
    items = []
    for x in raw[:limit] if limit else raw:
        sessions = []
        for when, turns in zip(x["haystack_dates"], x["haystack_sessions"]):
            d = parse_date(when)
            sessions.append((d, [f"[{d.isoformat()}] {t['role']}: {t['content'].strip()}" for t in turns
                                 if t.get("content", "").strip()]))
        sessions.sort(key=lambda s: s[0])
        items.append(Item(x["question_id"], x["question_type"], x["question"], str(x["answer"]),
                          parse_date(x["question_date"]), sessions))
    return items
