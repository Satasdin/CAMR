"""Development only: tell one Long Haul to the engine once and keep an APFS clone of its memory at each cut, so the
desk can be tuned on the saved memories without telling the history again (DECISIONS.md, E-61 onward).

    CAMR_MEASURING=... .venv/bin/python scripts/dev_ingest.py --dir ../work/haul/s2 --model qwen3-4b \
        --cuts 256K 1M --out ../work/memories/dev-s2-4b

Each snapshot is ``<out>/<cut>.nosync/project/longhaul``, saved (index, vault, tiers) before the clone. Seed-1 is
never told here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # run as a script from v2: camr_engine is beside it

from camr_engine.bench.local import Engine, LONGHAUL_INTRO, Loader
from camr_engine.bench.longhaul import CUTS, line
from camr_engine.bench.haul.script import load_events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--model", default="qwen3-4b")
    ap.add_argument("--cuts", nargs="+", default=["256K", "1M"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--notes", choices=("all", "hot"), default="all",
                    help="'hot': moments kept as words, notes only for rooms questions wake (memory.NOTES)")
    ap.add_argument("--disk-gb", type=float, help="the disk budget for awake room files, in GB (default: the bench's)")
    a = ap.parse_args()
    seed = json.loads((a.dir / "manifest.json").read_text())["seed"]
    if seed == 1:
        raise SystemExit("seed 1 is held out: development memories come from another seed")
    events = load_events(a.dir)
    a.out.mkdir(parents=True, exist_ok=True)
    kw = {"notes": a.notes} | ({"disk_bytes": int(a.disk_gb * 10**9)} if a.disk_gb is not None else {})
    e = Engine(a.model, loader=Loader(), intro=LONGHAUL_INTRO, **kw)
    work = a.out / "ingest.nosync"
    e.open(work)
    told, t0 = 0, time.perf_counter()
    log = {"seed": seed, "model": a.model, "notes": a.notes, "disk_gb": a.disk_gb, "cuts": {}}
    try:
        for name in a.cuts:
            limit = CUTS[name]
            while told < len(events) and events[told]["cum_tokens"] <= limit:
                ev = events[told]
                e.tell(line(ev), ev["day"])
                told += 1
            e.memory.save()
            snap = a.out / f"{name}.nosync"
            subprocess.run(["cp", "-c", "-R", str(work), str(snap)], check=True)
            log["cuts"][name] = {"events": told, "tokens": events[told - 1]["cum_tokens"], "day": e.days.day,
                                 "today": str(e.days.now()), "seconds": round(time.perf_counter() - t0, 1),
                                 "status": e.status()}
            (a.out / "ingest.json").write_text(json.dumps(log, indent=1, default=str))
            print(name, log["cuts"][name]["events"], "events", log["cuts"][name]["seconds"], "s", flush=True)
    finally:
        e.close()
    return 0


if __name__ == "__main__":
    from camr_engine.app.measuring import measuring

    with measuring("dev-ingest"):
        raise SystemExit(main())
