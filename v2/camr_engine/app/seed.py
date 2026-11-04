"""Fill the Mac app's memory with months of a project before a demo: the Long Haul's first ``--tokens`` told into
the global reach of one model's app memory, moment by moment, as the Long Haul's engine contender tells them.

    python -m camr_engine.app.seed --model mlx-community/Qwen3-4B-Instruct-2507-4bit --tokens 256000

The Mac app keeps each model's reaches under ``~/.camr/app/<model>/`` (its memory folder is ``default`` inside), and
every chat reads the global reach, so the app answers about Mama Njeri's Kitchen once this is done. The rooms are the
model's own notes: seed the model the app will load.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path


def app_root(model: str) -> Path:
    return Path.home() / ".camr" / "app" / model.split("/")[-1]


def seed(model: str, haul: Path, tokens: int, root: Path | None = None, reach: str = "global") -> dict:
    from camr_engine.bench.haul.script import load_events
    from camr_engine.bench.local import _Days
    from camr_engine.bench.longhaul import line
    from camr_engine.memory import Memory
    from camr_engine.models import Embedder, Reader
    from camr_engine.reach import Reach

    root = root or app_root(model)
    events = [e for e in load_events(haul) if e["cum_tokens"] <= tokens]
    r = Reach.parse(reach) if ":" in reach else Reach(reach)
    memory = Memory(Reader(model), Embedder(), r.path(root), vault=True, reach=r.label)
    days = _Days(None, True)
    t, kept = time.perf_counter(), 0
    for i, e in enumerate(events, 1):
        moment = days.moment(line(e), e["day"])
        if moment is not None:
            memory.remember(moment, e["day"], date=days.today)
            kept += 1
        if i % 250 == 0:
            print(f"{i}/{len(events)} events, {e['cum_tokens']:,} tokens, {time.perf_counter() - t:.0f} s", flush=True)
    memory.save()
    out = {"root": str(root), "reach": r.label, "moments": kept, "rooms": len(memory.rooms.rooms),
           "tokens": events[-1]["cum_tokens"] if events else 0, "seconds": round(time.perf_counter() - t, 1)}
    memory.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.app.seed")
    ap.add_argument("--model", default="mlx-community/Qwen3-4B-Instruct-2507-4bit")
    ap.add_argument("--haul", type=Path, default=Path(__file__).resolve().parents[3] / "work" / "haul" / "s1")
    ap.add_argument("--tokens", type=int, default=256_000)
    ap.add_argument("--reach", default="global")
    ap.add_argument("--root", type=Path)
    a = ap.parse_args(argv)
    print(seed(a.model, a.haul, a.tokens, a.root, a.reach))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
