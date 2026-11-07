"""python -m camr_engine.bench.rag_n8n {longhaul,up,down,status,build}

    longhaul --dir ../work/haul/s2 --cuts 2M [--k 8] [--budget 720] [--limit N] [--fresh]
    up        bring n8n + Qdrant up, set the local owner, import and publish the workflows
    down      stop the stack (its data stays in work/n8n)
    status    what the stack holds and costs now
    build     rewrite workflows/*.json from js/rag.js and build.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from camr_engine.bench.rag_n8n import build


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.rag_n8n")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("longhaul", help="the n8n RAG pipeline through the Long Haul's checkpoints")
    h.add_argument("--dir", type=Path, required=True, help="a built Long Haul (work/haul/<name>)")
    h.add_argument("--cuts", nargs="+", required=True, help="some of 64K 256K 1M 2M 3M 4M 8M 16M")
    h.add_argument("--k", type=int, default=build.K, help=f"chunks taken from Qdrant (default {build.K})")
    h.add_argument("--budget", type=int, default=build.BUDGET,
                   help=f"memory tokens per question (default {build.BUDGET}, CAMR's own at 2M)")
    h.add_argument("--order", choices=("date", "score"), default=build.ORDER)
    h.add_argument("--num-ctx", type=int, default=build.NUM_CTX)
    h.add_argument("--limit", type=int, help="at most this many questions per checkpoint, every family in turn")
    h.add_argument("--fresh", action="store_true", help="drop the collection and ingest the history again")
    h.add_argument("--records", type=Path, help="where the record goes (default v2/records/bench)")
    sub.add_parser("up")
    sub.add_parser("down")
    sub.add_parser("status")
    sub.add_parser("build")
    return ap


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    if a.cmd == "build":
        for p in build.write():
            print(p)
        return 0
    from camr_engine.bench.rag_n8n import stack

    if a.cmd == "up":
        print(json.dumps(stack.up(), indent=1))
        return 0
    if a.cmd == "down":
        stack.down()
        return 0
    if a.cmd == "status":
        w = stack.RamWatch()
        total, detail = w.sample()
        print(json.dumps({"running": stack.running(), "ram_gb": round(total / 1e9, 3), "ram": detail,
                          "disk": stack.disk()}, indent=1, default=str))
        return 0
    from camr_engine.bench.rag_n8n.runner import longhaul

    if a.budget < 1 or a.k < 1:
        raise SystemExit("k and budget are positive")
    if a.budget + 1500 > a.num_ctx:
        raise SystemExit(f"a budget of {a.budget} tokens with a page answer does not fit num_ctx {a.num_ctx}")
    rec = longhaul(a.dir, a.cuts, k=a.k, budget=a.budget, order=a.order, limit=a.limit, fresh=a.fresh,
                   num_ctx=a.num_ctx, **({"records": a.records} if a.records else {}))
    print(rec.get("path"))
    return 1 if rec.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
