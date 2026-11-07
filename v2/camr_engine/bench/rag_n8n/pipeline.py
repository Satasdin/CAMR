"""The n8n workflows' logic in Python: the same chunking, choosing and prompt as js/rag.js, which the Code nodes run.

The workflows are the pipeline; this module is its reference copy, for the tests (which run both on the same input
and require the same output) and for the runner, which sizes each event's dated line in Qwen3 tokens before sending
it, so the workflow packs chunks by real token counts and not by a guess.
"""

from __future__ import annotations

import math
from typing import Any

CHARS_PER_TOKEN = 3.5
PART_STRIDE = 64
CHUNK_TOKENS = 512  # the conventional chunk size


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def head(e: dict) -> str:
    day = "" if e.get("day") is None else f", day {e['day']}"
    return f"[{e['date']}{day}] "


def line(e: dict) -> str:
    """An event's dated line, as a chunk holds it (before any cut)."""
    return head(e) + e["text"]


def split_text(text: str, max_chars: int) -> list[str]:
    out, rest = [], text
    while len(rest) > max_chars:
        cut = rest.rfind("\n", 0, max_chars + 1)
        if cut < max_chars / 2:
            cut = rest.rfind(" ", 0, max_chars + 1)
        if cut < max_chars / 2:
            cut = max_chars
        out.append(rest[:cut])
        rest = rest[cut:].lstrip("\n ")
    if rest:
        out.append(rest)
    return out


def pieces(e: dict, limit: int) -> list[dict]:
    h = head(e)
    full = h + e["text"]
    given = e.get("tokens")
    n = given if isinstance(given, int) and not isinstance(given, bool) and given > 0 else estimate_tokens(full)
    if n <= limit:
        return [{"text": full, "tokens": n, "part": 0}]
    per_char = n / len(full)
    max_chars = max(1, math.floor(limit / per_char) - len(h))
    return [{"text": h + p, "tokens": min(limit, math.ceil((len(h) + len(p)) * per_char)), "part": j}
            for j, p in enumerate(split_text(e["text"], max_chars))]


def chunk_events(events: list[dict], limit: int = CHUNK_TOKENS) -> list[dict]:
    chunks: list[dict] = []
    cur: dict[str, Any] | None = None
    for e in events:
        for p in pieces(e, limit):
            if cur is not None and cur["tokens"] + p["tokens"] > limit:
                chunks.append(cur)
                cur = None
            if cur is None:
                cur = {"id": e["i"] * PART_STRIDE + p["part"], "lines": [], "tokens": 0, "event_ids": [],
                       "date_from": e["date"], "date_to": e["date"], "day_from": e.get("day"), "day_to": e.get("day")}
            cur["lines"].append(p["text"])
            cur["tokens"] += p["tokens"]
            if not cur["event_ids"] or cur["event_ids"][-1] != e["i"]:
                cur["event_ids"].append(e["i"])
            cur["date_to"], cur["day_to"] = e["date"], e.get("day")
    if cur is not None:
        chunks.append(cur)
    return [{"id": c["id"], "text": "\n".join(c["lines"]), "tokens": c["tokens"], "event_ids": c["event_ids"],
             "date_from": c["date_from"], "date_to": c["date_to"], "day_from": c["day_from"], "day_to": c["day_to"]}
            for c in chunks]


def select_chunks(hits: list[dict], k: int, budget: int, order: str = "date") -> dict:
    picked, total = [], 0
    for h in hits[:k]:
        n = h["payload"]["tokens"]
        if total + n > budget:
            continue
        picked.append(h)
        total += n
    if order == "date":
        picked = sorted(picked, key=lambda h: h["id"])
    return {"picked": picked, "tokens": total}


def notes_text(picked: list[dict]) -> str:
    return "".join(h["payload"]["text"] + "\n" for h in picked)


def system_prompt(intro: str, notes: str, today: str | None, then: str | None) -> str:
    date = f"\nToday is {today}." if today else ""
    return f"{intro}\n\nNotes:\n{notes}End of notes.{date}" + (f"\n\n{then}" if then else "")
