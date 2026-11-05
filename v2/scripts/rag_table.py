"""Print the comparison table of Long Haul / desk records: right per cut, by family, first word, prefill tokens,
memory in view, retrieval, footprint and disk (DECISIONS.md, E-61 onward).

    .venv/bin/python scripts/rag_table.py records/bench/2026-11-05/*-longhaul-*.json records/bench/2026-11-05/*-desk-*.json
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter

FAMS = ("fact", "changed", "two_hop", "maths", "page", "code", "lookalike", "never")


def p50(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 3) if xs else None


def rows(path: str):
    r = json.load(open(path))
    name = r["contender"]["name"]
    for cp in r.get("checkpoints", []):
        a = cp["answers"]
        s = cp["summary"]["all"]
        ex = [x.get("extra", {}) for x in a]
        fam = {f: f"{cp['summary'][f]['right']}/{cp['summary'][f]['questions']}" for f in FAMS if f in cp["summary"]}
        stale = Counter(x["verdict"] for x in a)["stale"]
        status = cp.get("status", {})
        yield {"name": name, "cut": cp["name"], "right": s["right"], "of": s["questions"], "fams": fam,
               "stale": stale, "ttft": s["ttft_s"]["p50"], "ttft90": s["ttft_s"]["p90"], "total": s["total_s"]["p50"],
               "prefill": p50(e.get("prefill_tokens") for e in ex), "view": p50(e.get("memory_in_view") for e in ex),
               "notes": p50(e.get("memory_notes") for e in ex), "words": p50(e.get("memory_words") for e in ex),
               "retr": s["retrieval_ms"]["p50"], "asleep": sum(bool(e.get("asleep")) for e in ex),
               "rooms": p50(e.get("rooms_laid") for e in ex), "fp": cp.get("footprint_gb"),
               "peakfp": status.get("peak_footprint_gb"), "disk": s.get("disk_gb"),
               "ingest_tps": cp.get("ingest", {}).get("tokens_per_s"), "path": path}


def main(paths):
    out = [x for p in paths for x in rows(p)]
    for x in out:
        print(f"{x['name']:<44} {x['cut']:>4} {x['right']:>3}/{x['of']:<3} stale {x['stale']:<2} ttft {x['ttft']} "
              f"(p90 {x['ttft90']}) total {x['total']} prefill {x['prefill']} view {x['view']} (notes {x['notes']} "
              f"words {x['words']}) rooms {x['rooms']} asleep {x['asleep']} retr {x['retr']} ms fp {x['fp']} "
              f"peak {x['peakfp']} disk {x['disk']} ingest {x['ingest_tps']} | "
              + " ".join(f"{k}:{v}" for k, v in x["fams"].items()))


if __name__ == "__main__":
    main(sys.argv[1:])
