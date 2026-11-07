"""The Long Haul made longer: the same 110 days, then more working days of ordinary work and nothing new to remember.

Every probe stays where it was planted, inside the first 2M tokens. The days after day 110 are noise only: chat, logs,
code, docs, notes, WhatsApp, decisions and lessons, from the same generators with random streams of their own. So a
question asked at 3M or 4M is the question asked at 2M with one or two million more tokens of history on top of it.
The longer script passes the same fairness checks as the original.

    python -m camr_engine.bench.haul.extend --seed 1 --tokens 4010000 --out work/haul/s1-4m
"""

from __future__ import annotations

import argparse
import hashlib
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from camr_engine.bench.haul import tokens as tok
from camr_engine.bench.haul.noise import Noise
from camr_engine.bench.haul.script import (DAYS, NOISE_MIX, Haul, _verify, askable_at, build, calendar, write)
from camr_engine.bench.haul.words import long_date
from camr_engine.bench.haul.world import build_world

CUTS = {"64K": 64_000, "256K": 256_000, "1M": 1_000_000, "2M": 2_000_000, "3M": 3_000_000, "4M": 4_000_000,
        "8M": 8_000_000, "16M": 16_000_000}
TARGET = 4_010_000  # a little past the 4M cut


def extend(seed: int = 1, target: int = TARGET, count: Callable[[str], int] | None = None, base: Haul | None = None,
           stream: int = 0) -> Haul:
    """The Long Haul for ``seed``, made ``target`` tokens long with days of noise after day 110. ``stream`` picks
    another random stream for the new days (when one fails the fairness checks)."""
    count = count or tok.counter()
    base = base or build(seed, count=count)
    events = [dict(e) for e in base.events]
    total = events[-1]["cum_tokens"]
    per_day = total / DAYS
    days = DAYS + max(1, math.ceil((target - total) / per_day))
    dates = calendar(days)
    noise = Noise(random.Random(f"{seed}:noise:more{stream}"), build_world(random.Random(f"{seed}:world")), dates)
    rng = random.Random(f"{seed}:days:more{stream}")
    weights = [rng.uniform(0.7, 1.3) for _ in range(days - DAYS)]
    budget = [w * (target - total) / sum(weights) for w in weights]
    fill = random.Random(f"{seed}:fill:more{stream}")
    kinds, mix = zip(*NOISE_MIX)

    def emit(day: int, kind: str, role: str, text: str) -> None:
        nonlocal total
        n = count(text)
        total += n
        events.append({"i": len(events), "day": day, "kind": kind, "role": role, "text": text, "tokens": n,
                       "cum_tokens": total})

    end = total
    for k, day in enumerate(range(DAYS + 1, days + 1)):
        end += budget[k]
        emit(day, "day", "system", f"Day {day} · {long_date(dates[day - 1])}")
        while total < end:
            for kind, role, text in getattr(noise, fill.choices(kinds, mix)[0])(day):
                emit(day, kind, role, text)
    _verify(events, base.probes, base.configs)
    return Haul(seed, events, base.probes, manifest(base, events, days, dates), base.configs)


def manifest(base: Haul, events: list[dict], days: int, dates) -> dict:
    """The original manifest, with the longer script's counts and every cut that fits it."""
    m = dict(base.manifest)
    cuts = {}
    for name, limit in CUTS.items():
        if limit > events[-1]["cum_tokens"]:
            continue
        inside = [e for e in events if e["cum_tokens"] <= limit]
        cuts[name] = {"limit": limit, "tokens": inside[-1]["cum_tokens"], "events": len(inside),
                      "last_day": inside[-1]["day"],
                      "probes": dict(Counter(p["family"] for p in base.probes if askable_at(p, limit)))}
    kinds: dict[str, dict] = defaultdict(lambda: {"events": 0, "tokens": 0})
    for e in events:
        kinds[e["kind"]]["events"] += 1
        kinds[e["kind"]]["tokens"] += e["tokens"]
    m.update(days=days, end=dates[days - 1].isoformat(), events=len(events), tokens=events[-1]["cum_tokens"],
             cuts=cuts, kinds=dict(kinds), extends=base.manifest["script_sha"], planted_days=DAYS,
             script_sha=hashlib.sha256("".join(e["text"] for e in events).encode()).hexdigest()[:16])
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.haul.extend")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tokens", type=int, default=TARGET)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    count = tok.counter()
    base = build(a.seed, count=count)
    for stream in range(10):
        try:
            haul = extend(a.seed, a.tokens, count=count, base=base, stream=stream)
            break
        except AssertionError as e:
            print(f"stream {stream} fails the fairness checks ({str(e)[:120]}); trying the next")
    else:
        return 1
    write(haul, a.out)
    print(f"{a.out}: {haul.manifest['events']} events, {haul.manifest['tokens']:,} tokens, {haul.manifest['days']} "
          f"days; cuts {', '.join(haul.manifest['cuts'])}; probes planted by day {DAYS}, unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
