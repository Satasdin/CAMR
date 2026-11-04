"""What the desk holds for a few 2M fact questions, and the answer with variations of the prompt."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/p3wrky/Desktop/camr-build-wt/v2")
from engram.bench.local import LONGHAUL_INTRO, MODELS, Loader, _Memory, hint, haul_dates  # noqa: E402
from engram.swap import Tiers  # noqa: E402

W = Path("/Users/p3wrky/Desktop/camr-build-wt")
CLONE = W / "work/memories/wake-test-2M.nosync"
probes = {json.loads(l)["id"]: json.loads(l) for l in open(W / "work/haul/s1/probes.jsonl")}
loader = Loader()
reader, embedder = loader.reader(MODELS["qwen3-1.7b"]), loader.embedder()
m = _Memory(reader, embedder, CLONE / "project/longhaul", intro=LONGHAUL_INTRO, reach="project:longhaul",
            vault=True, core=True, tiers=Tiers(ram_bytes=2 * 10**9, disk_bytes=40 * 10**9, wake=True),
            metrics=True, log=False)
today = haul_dates()(110)
for qid in ("fact-381", "fact-065", "fact-243"):
    p = probes[qid]
    rc = m.choose(p["ask"])
    print("=" * 100)
    print(qid, p["ask"], "->", p["answer"], "| room", rc.room)
    head, rest = m.prompt(today, p["ask"], hint("fact"), None)
    print("HEAD:", reader.tok.decode(head)[-400:] if hasattr(reader, "tok") else head[-50:])
    print("REST:", reader.tok.decode(rest) if hasattr(reader, "tok") else rest)
    for mid in m.rooms.rooms[rc.room].members:
        t = m.rooms.moments[mid].text
        mark = "  <== PLANTED" if p["answer"] in t else ""
        print("  room:", t[:150].replace("\n", " "), mark)
    for mid in rc.closest:
        t = m.rooms.moments[mid].text
        print("  closest:", t[:150].replace("\n", " "), "  <== PLANTED" if p["answer"] in t else "")
    r = m.answer(p["ask"], today, then=hint("fact"), max_tokens=60, chosen=rc, day=110, record=True)
    print("ANSWER:", repr(r.text))
