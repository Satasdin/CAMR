"""The 2M recall questions asked twice of the engine's own 2M memory: once with asleep rooms read as words (as the
Long Haul run did), once with the asked room woken first (its notes written again from its words).

Runs on a clone of the memory folder (APFS clone: instant, no space), so the run's own folder is left as it was."""
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/p3wrky/Desktop/camr-build-wt/v2")
from engram.bench.local import LONGHAUL_INTRO, MODELS, Loader, _Memory, hint, haul_dates, max_tokens  # noqa: E402
from engram.bench.longhaul import grader  # noqa: E402
from engram.swap import Tiers  # noqa: E402

W = Path("/Users/p3wrky/Desktop/camr-build-wt")
SRC = W / "work/memories/longhaul-engine-qwen3-1.7b-20261104-044359.nosync"
CLONE = W / "work/memories/wake-test-2M.nosync"
FAMILIES = ("fact", "changed", "two_hop", "lookalike")

rec = json.loads(Path(sorted(glob.glob(str(W / "v2/records/bench/2026-11-04/*longhaul-engine-qwen3-1.7b.json")))[-1]).read_text())
cp = [c for c in rec["checkpoints"] if c["name"] == "2M"][0]
probes = {json.loads(line)["id"]: json.loads(line) for line in open(W / "work/haul/s1/probes.jsonl")}
asked = [a for a in cp["answers"] if a["family"] in FAMILIES]

if CLONE.exists():
    subprocess.run(["rm", "-rf", str(CLONE)], check=True)
subprocess.run(["cp", "-cR", str(SRC), str(CLONE)], check=True)

loader = Loader()
reader, embedder = loader.reader(MODELS["qwen3-1.7b"]), loader.embedder()
today = haul_dates()(110)
out = {}
for wake in (False, True):
    m = _Memory(reader, embedder, CLONE / "project/longhaul", intro=LONGHAUL_INTRO, reach="project:longhaul",
                vault=True, core=True, tiers=Tiers(ram_bytes=2 * 10**9, disk_bytes=40 * 10**9, wake=wake),
                metrics=True, log=False)
    rows = []
    for a in asked:
        q = {"probe": probes[a["id"]], "question": a["question"]}
        t = time.perf_counter()
        rc = m.choose(a["question"])
        reply = m.answer(a["question"], today, then=hint(a["family"]), max_tokens=max_tokens(a["family"]), chosen=rc,
                         started=t, day=110, record=True)
        g = grader(q, reply.text)
        rows.append({"id": a["id"], "family": a["family"], "right": g["right"], "verdict": g["verdict"],
                     "asleep": rc.asleep, "woke": bool(rc.seconds.get("wake")), "ttft_s": round(reply.ttft_s, 3),
                     "wake_s": round(rc.seconds.get("wake", 0.0), 3), "answer": reply.text[:120]})
        print(wake, rows[-1], flush=True)
    out["wake" if wake else "words"] = rows
    m.close() if hasattr(m, "close") else None

for k, rows in out.items():
    right = sum(r["right"] for r in rows)
    print(k, "right", right, "/", len(rows), "by family",
          {f: f"{sum(r['right'] for r in rows if r['family'] == f)}/{sum(1 for r in rows if r['family'] == f)}"
           for f in FAMILIES})
Path(W / "work/wake-test-2M.json").write_text(json.dumps(out, indent=1))
