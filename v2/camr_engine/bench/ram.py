"""What the engine's process really holds while it reads a long history, with MLX's buffer cache capped or not.

Each setting runs in a fresh process (the cap is set when a model loads): the engine reads the first ``--tokens`` of
the Long Haul, and the process's physical footprint (camr_engine.models.footprint_bytes: what Activity Monitor shows,
compressed pages included) is sampled as it goes, beside MLX's own active, cached and peak memory. Then a few short
questions are asked, so the cap's cost in speed shows too.

    python -m camr_engine.bench.ram --model qwen3-1.7b --dir ../work/haul/s1 --tokens 256000 --cache off 1
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

SAMPLE_EVERY = 250  # events between footprint samples
QUESTIONS = 10


def child(model: str, folder: Path, tokens: int, memory: Path) -> dict:
    import mlx.core as mx

    from camr_engine.bench.contender import max_tokens
    from camr_engine.bench.haul.script import load_events, load_probes
    from camr_engine.bench.local import haul_contender, speed_questions
    from camr_engine.bench.longhaul import grader, line
    from camr_engine.models import CACHE_GB, footprint_bytes

    events = [e for e in load_events(folder) if e["cum_tokens"] <= tokens]
    c = haul_contender(f"engine:{model}")
    c.open(memory)
    samples, t0 = [], time.perf_counter()

    def sample(i: int) -> None:
        samples.append({"events": i, "tokens": events[i - 1]["cum_tokens"], "s": round(time.perf_counter() - t0, 1),
                        "footprint_gb": round((footprint_bytes() or 0) / 1e9, 3),
                        "mlx_active_gb": round(mx.get_active_memory() / 1e9, 3),
                        "mlx_cache_gb": round(mx.get_cache_memory() / 1e9, 3),
                        "mlx_peak_gb": round(mx.get_peak_memory() / 1e9, 3)})

    for i, e in enumerate(events, start=1):
        c.tell(line(e), e["day"])
        if i % SAMPLE_EVERY == 0 or i == len(events):
            sample(i)
    ingest_s = time.perf_counter() - t0
    qs = speed_questions(load_probes(folder), events[-1]["cum_tokens"], n=QUESTIONS)
    answers = []
    for q in qs:
        a = c.ask(q["question"], max_tokens=max_tokens(q["family"]), family=q["family"])
        g = grader(q, a.text)
        answers.append({"id": q["id"], "right": g["right"], "ttft_s": a.metrics["ttft_s"],
                        "total_s": a.metrics["total_s"], "peak_ram_gb": a.metrics["peak_ram_gb"]})
    sample(len(events))
    c.close()
    shutil.rmtree(memory, ignore_errors=True)  # tens of GB of notes, needed only for this measurement
    ttft = sorted(a["ttft_s"] for a in answers if a["ttft_s"] is not None)
    return {"cache_gb": CACHE_GB, "events": len(events), "tokens": events[-1]["cum_tokens"],
            "ingest_s": round(ingest_s, 1), "tokens_per_s": round(events[-1]["cum_tokens"] / ingest_s, 1),
            "footprint_peak_gb": max(s["footprint_gb"] for s in samples), "samples": samples, "answers": answers,
            "right": sum(a["right"] for a in answers), "ttft_p50_s": ttft[len(ttft) // 2] if ttft else None}


def main(argv: Sequence[str] | None = None) -> int:
    from camr_engine.bench.contender import RECORDS, environment, record_path, write_record
    from camr_engine.bench.local import MEMORIES

    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.ram")
    ap.add_argument("--model", default="qwen3-1.7b")
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--tokens", type=int, default=256_000)
    ap.add_argument("--cache", nargs="+", default=["off", "1"], help="cache caps in GB to compare, or off")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--records", type=Path, default=RECORDS)
    a = ap.parse_args(argv)
    if a.child:
        a.out.write_text(json.dumps(child(a.model, a.dir, a.tokens, MEMORIES / f"ram-{os.getpid()}.nosync")))
        return 0
    started = dt.datetime.now()
    runs = []
    for cap in a.cache:
        out = MEMORIES / f"ram-{cap}.json"
        env = {**os.environ, "CAMR_MLX_CACHE_GB": cap}
        rc = subprocess.run([sys.executable, "-m", "camr_engine.bench.ram", "--child", "--model", a.model, "--dir",
                             str(a.dir), "--tokens", str(a.tokens), "--out", str(out)], env=env).returncode
        runs.append(json.loads(out.read_text()) if rc == 0 else {"cache_gb": cap, "failed": rc})
        print(cap, {k: runs[-1].get(k) for k in ("footprint_peak_gb", "tokens_per_s", "ttft_p50_s", "right")})
    record = {"kind": "bench", "task": "ram", "model": a.model, "tokens": a.tokens, "environment": environment(),
              "started": started.isoformat(timespec="seconds"), "runs": runs,
              "finished": dt.datetime.now().isoformat(timespec="seconds")}
    print(write_record(record, record_path("ram", f"engine:{a.model}", started, a.records)))
    return 0


if __name__ == "__main__":
    if "--child" in sys.argv:  # the parent holds the measuring flag
        raise SystemExit(main())
    from camr_engine.app.measuring import measuring

    with measuring("ram"):
        raise SystemExit(main())
