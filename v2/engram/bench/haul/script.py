"""Building the Long Haul: 110 working days of one project, at least 2,000,000 Qwen3 tokens, fixed by its seed.

The days are laid out with a token budget each (the first week is quieter). Planted events go in at their
position within the day, and noise fills the rest. Outputs:

  script.jsonl   one event per line: i, day, kind, role, text, tokens, cum_tokens
  probes.jsonl   one probe per line: id, family, ask, answer, grader, event (the planted event's index),
                 planted_at (its cumulative tokens), events (every event it needs), ready_at (tokens once all are in)
  manifest.json  counts per family, tokens and askable probes per cut, tokens per kind
"""

from __future__ import annotations

import bisect
import datetime as dt
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import accumulate
from pathlib import Path
from typing import Callable

from engram.bench.haul import tokens as tok
from engram.bench.haul.grade import names
from engram.bench.haul.grade import norm as grade_norm
from engram.bench.haul.noise import Noise
from engram.bench.haul.probes import CONFIGS, COUNTS, NEVER_ENTITY, Planner
from engram.bench.haul.words import FIRST, SURNAMES, long_date
from engram.bench.haul.world import build_world

DAYS = 110
START = dt.date(2025, 9, 22)  # a Monday
HOLIDAYS = {dt.date(2025, 10, 20), dt.date(2025, 12, 12), dt.date(2025, 12, 25), dt.date(2025, 12, 26),
            dt.date(2026, 1, 1)}
CUTS = {"64K": 64_000, "256K": 256_000, "1M": 1_000_000, "2M": 2_000_000}
TARGET = 2_010_000  # a little past the 2M cut, so everything planted sits inside it
LONGEST = 400  # working days in the longest script (engram.bench.haul.extend); the first 110 are these
VERSION = 2  # 2: no config value in the noise, renamed values that clashed with their questions
NOISE_MIX = [("chat", 13), ("log", 3.2), ("code", 9), ("doc", 10), ("notes", 6.5), ("whatsapp", 4),
             ("decision", 5), ("lesson", 3.2)]  # calls, weighted so chat is about 30% of the tokens and logs 18%


@dataclass
class Haul:
    seed: int
    events: list[dict]
    probes: list[dict]
    manifest: dict
    configs: list[tuple[str, list[str], int | None]] = field(default_factory=list)  # (setting, values, told at)


def calendar(days: int = DAYS) -> list[dt.date]:
    """The working days: Monday to Friday, without Kenyan public holidays."""
    out, d = [], START
    while len(out) < days:
        if d.weekday() < 5 and d not in HOLIDAYS:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def budgets(rng: random.Random, target: int, days: int = DAYS) -> list[float]:
    """Tokens per day: varied, the first week at about half, summing to ``target``."""
    w = [rng.uniform(0.7, 1.3) * (0.45 if d <= 5 else 1.0) for d in range(1, days + 1)]
    s = sum(w)
    return [x * target / s for x in w]


def build(seed: int = 1, target: int = TARGET, count: Callable[[str], int] | None = None) -> Haul:
    """The whole Long Haul for ``seed``. ``count`` counts tokens (default: the Qwen3 tokenizer)."""
    count = count or tok.counter()
    dates = calendar()
    world = build_world(random.Random(f"{seed}:world"))
    noise = Noise(random.Random(f"{seed}:noise"), world, dates)
    per_day = budgets(random.Random(f"{seed}:days"), target)
    ends = list(accumulate(per_day))

    def where(depth: float) -> tuple[int, float]:
        for d, end in enumerate(ends, start=1):
            if depth <= end:
                return d, (depth - (end - per_day[d - 1])) / per_day[d - 1]
        return DAYS, 1.0

    planner = Planner(seed, world, noise, dates, where, target)
    planner.run()
    by_day: dict[int, list] = defaultdict(list)
    for p in planner.plants:
        by_day[p.day].append(p)
    for plants in by_day.values():
        plants.sort(key=lambda p: (p.pos, p.ref))

    fill = random.Random(f"{seed}:fill")
    kinds, weights = zip(*NOISE_MIX)
    events: list[dict] = []
    where_ref: dict[str, int] = {}
    total = 0

    def emit(day: int, kind: str, role: str, text: str) -> None:
        nonlocal total
        n = count(text)
        total += n
        events.append({"i": len(events), "day": day, "kind": kind, "role": role, "text": text, "tokens": n,
                       "cum_tokens": total})

    for day in range(1, DAYS + 1):
        start, end = total, ends[day - 1]
        emit(day, "day", "system", f"Day {day} · {long_date(dates[day - 1])}")
        queue = list(by_day.get(day, []))
        while True:
            frac = (total - start) / max(1.0, end - start)
            while queue and queue[0].pos <= frac:
                p = queue.pop(0)
                where_ref[p.ref] = len(events) + p.key % len(p.events)
                for kind, role, text in p.events:
                    emit(day, kind, role, text)
            if total >= end:
                break
            genre = fill.choices(kinds, weights)[0]
            for kind, role, text in getattr(noise, genre)(day):
                emit(day, kind, role, text)
        for p in queue:
            where_ref[p.ref] = len(events) + p.key % len(p.events)
            for kind, role, text in p.events:
                emit(day, kind, role, text)

    day_end: dict[int, int] = {}
    for e in events:
        day_end[e["day"]] = e["cum_tokens"]
    probes = [_finish(p, events, where_ref, day_end) for p in planner.probes]
    probes.sort(key=lambda p: (list(COUNTS).index(p["family"]), p["id"]))
    manifest = _manifest(seed, events, probes, planner)
    configs = [(np_, [str(v) for v in values], where_ref[planner.configs[np_]] if planner.configs.get(np_) else None)
               for np_, _, values in CONFIGS]
    _verify(events, probes, configs)
    return Haul(seed, events, probes, manifest, configs)


def _finish(p: dict, events: list[dict], where_ref: dict[str, int], day_end: dict[int, int]) -> dict:
    p = dict(p)
    refs = p.pop("refs")
    idx = sorted(where_ref[r] for r in refs)
    g = p["grader"]
    if g["type"] == "timeline":
        values = []
        for v in g["values"]:
            i = where_ref[v["ref"]]
            values.append({**{k: x for k, x in v.items() if k != "ref"}, "event": i, "tokens": events[i]["cum_tokens"]})
        g = dict(g, values=values)
        if g["on_day"] is not None:
            g["day_over_at"] = day_end[g["on_day"]]
            right = [v for v in values if v["day"] <= g["on_day"]][-1]
        else:
            right = values[-1]
        p["grader"] = g
        main = right["event"]
        ready = max(right["tokens"], g.get("day_over_at", 0)) if g["on_day"] is not None else values[-1]["tokens"]
    elif g["type"] == "page":
        g = dict(g, timeline=[{"value": v["value"], "event": where_ref[v["ref"]],
                               "tokens": events[where_ref[v["ref"]]]["cum_tokens"],
                               "day": events[where_ref[v["ref"]]]["day"]} for v in g["timeline"]])
        p["grader"] = g
        main = g["timeline"][-1]["event"]
        ready = g["timeline"][0]["tokens"]
    else:
        main = where_ref[refs[0]] if p["family"] == "lookalike" else (idx[-1] if idx else None)
        ready = events[idx[-1]]["cum_tokens"] if idx else None
    p["events"] = idx
    p["event"] = main
    p["planted_at"] = events[main]["cum_tokens"] if main is not None else None
    p["ready_at"] = ready
    p["planted_day"] = events[main]["day"] if main is not None else None
    p.setdefault("sample", False)
    p.setdefault("ask_day", None)
    return p


def askable_at(p: dict, cut: int) -> bool:
    """Whether everything a probe needs is inside the first ``cut`` tokens."""
    from engram.bench.haul.sample import at_cut
    return at_cut(p, cut) is not None


def _manifest(seed: int, events: list[dict], probes: list[dict], planner: Planner) -> dict:
    cuts = {}
    for name, limit in CUTS.items():
        inside = [e for e in events if e["cum_tokens"] <= limit]
        cuts[name] = {"limit": limit, "tokens": inside[-1]["cum_tokens"], "events": len(inside),
                      "last_day": inside[-1]["day"],
                      "probes": dict(Counter(p["family"] for p in probes if askable_at(p, limit)))}
    kinds: dict[str, dict] = defaultdict(lambda: {"events": 0, "tokens": 0})
    for e in events:
        kinds[e["kind"]]["events"] += 1
        kinds[e["kind"]]["tokens"] += e["tokens"]
    digest = hashlib.sha256("".join(e["text"] for e in events).encode()).hexdigest()[:16]
    return {"name": "The Long Haul", "project": "Mama Njeri's Kitchen, Nairobi", "version": VERSION, "seed": seed,
            "tokenizer": tok.TOKENIZER, "days": DAYS, "start": START.isoformat(),
            "end": calendar()[-1].isoformat(), "events": len(events), "tokens": events[-1]["cum_tokens"],
            "families": dict(Counter(p["family"] for p in probes)), "decoys": planner.decoys, "cuts": cuts,
            "kinds": dict(kinds), "samples": [p["id"] for p in probes if p["sample"]], "script_sha": digest}


_NAME_NEAR_OTIENO = re.compile(r"\bOtieno\s+(" + "|".join(SURNAMES + FIRST) + r")\b|\b(" + "|".join(SURNAMES + FIRST)
                               + r")\s+Otieno\b")


def config_clashes(events: list[dict], configs: list[tuple[str, list[str], int | None]]) -> list[str]:
    """Where the script names a setting's possible value outside the one event that tells it (anywhere at all for a
    setting that is never told). Numbers are left out: they are everywhere. Empty when the settings are fair."""
    texts = [e["text"].casefold() for e in events]
    starts, at = [], 0
    for t in texts:
        starts.append(at)
        at += len(t) + 1
    low = "\n".join(texts)
    out = []
    for np_, values, told in configs:
        for v in values:
            if re.fullmatch(r"[\d.,]+", v):
                continue
            key = v.casefold()
            word = "_" + ("-" if re.search(r"[-_]", key) else "") + (":." if re.fullmatch(r"\d+:\d+", key) else "")
            i = low.find(key)
            while i >= 0:
                before = low[i - 1] if i else " "
                after = low[i + len(key)] if i + len(key) < len(low) else " "
                if not (before.isalnum() or before in word or after.isalnum() or after in word):
                    e = bisect.bisect_right(starts, i) - 1
                    if e != told:
                        out.append(f"{np_}: '{v}' in event {e}" + (" (never told)" if told is None else ""))
                        break
                i = low.find(key, i + 1)
    return out


def answer_clashes(probes: list[dict]) -> list[str]:
    """Probes whose own question names one of their values, so that restating the question would match."""
    out = []
    for p in probes:
        g = p["grader"]
        if g["type"] == "timeline":
            values = [a for v in g["values"] for a in v["accept"]]
        elif g["type"] == "exact":
            values = g["accept"] + g.get("stale", []) + g.get("reject", []) + g.get("others", [])
        else:
            continue
        hit = names(p["ask"], values, p["ask"])
        if hit:
            out.append(f"{p['id']}: '{hit}' is in its question {grade_norm(p['ask'])!r}")
    return out


def _verify(events: list[dict], probes: list[dict], configs: list | None = None) -> None:
    """Checks that would make a probe unfair. Raises on any failure."""
    if events[-1]["cum_tokens"] < CUTS["2M"]:
        raise AssertionError(f"only {events[-1]['cum_tokens']} tokens")
    ids = [p["id"] for p in probes]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate probe ids")
    late = [p["id"] for p in probes if (p["ready_at"] or 0) > CUTS["2M"] or (p["planted_at"] or 0) > CUTS["2M"]]
    if late:
        raise AssertionError(f"planted past the 2M cut: {late[:5]}")
    text = "\n".join(e["text"] for e in events)
    low = text.lower()
    said = [f"'{q}' but the script says '{w}'" for q, absent in NEVER_ENTITY for w in absent
            if re.search(r"\b" + re.escape(w.lower()) + r"\b", low)]
    if said:
        raise AssertionError("never-said " + "; ".join(said))
    m = _NAME_NEAR_OTIENO.search(text)
    if m:
        raise AssertionError(f"Otieno gets a name next to his: {m.group(0)!r}")
    clash = answer_clashes(probes) + config_clashes(events, configs or [])
    if clash:
        raise AssertionError("unfair values: " + "; ".join(clash[:8]))


def write(haul: Haul, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "script.jsonl", "w", encoding="utf-8") as f:
        for e in haul.events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(out / "probes.jsonl", "w", encoding="utf-8") as f:
        for p in haul.probes:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    (out / "manifest.json").write_text(json.dumps(haul.manifest, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")


def load_probes(out: Path) -> list[dict]:
    return [json.loads(line) for line in open(out / "probes.jsonl", encoding="utf-8")]


def load_events(out: Path) -> list[dict]:
    return [json.loads(line) for line in open(out / "script.jsonl", encoding="utf-8")]
