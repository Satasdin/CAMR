import json, sys, glob
from pathlib import Path
sys.path.insert(0, "/Users/p3wrky/Desktop/camr-build-wt/v2")
from engram.bench.local import LONGHAUL_INTRO, MODELS, Loader, _Memory, hint, haul_dates
from engram.bench.longhaul import grader
from engram.memory import INTRO
from engram.swap import Tiers
W = Path("/Users/p3wrky/Desktop/camr-build-wt")
CLONE = W / "work/memories/wake-test-2M.nosync"
probes = {json.loads(l)["id"]: json.loads(l) for l in open(W / "work/haul/s1/probes.jsonl")}
rec = json.loads(Path(sorted(glob.glob(str(W / "v2/records/bench/2026-11-04/*longhaul-engine-qwen3-1.7b.json")))[-1]).read_text())
loader = Loader(); reader, embedder = loader.reader(MODELS["qwen3-1.7b"]), loader.embedder()
m = _Memory(reader, embedder, CLONE / "project/longhaul", intro=LONGHAUL_INTRO, reach="project:longhaul",
            vault=True, core=True, tiers=Tiers(ram_bytes=2 * 10**9, disk_bytes=40 * 10**9, wake=True), metrics=True, log=False)
D = haul_dates()
SOFT = ("You answer questions about a project's history: one developer's log of chats, decisions, code, notes and "
        "lessons. Notes from that history come before each question; use them to answer. Answer \"I don't know\" "
        "only when nothing in the notes bears on the question. Keep each answer short unless the question asks for "
        "code or a page.")
WORDINGS = {"longhaul": LONGHAUL_INTRO, "intro": INTRO, "soft": SOFT}
for cut in ("256K", "2M"):
    cp = [c for c in rec["checkpoints"] if c["name"] == cut][0]
    qs = [a for a in cp["answers"] if a["family"] in ("fact", "changed", "never", "lookalike")]
    today = D(16 if cut == "256K" else 110)
    score = {k: {} for k in WORDINGS}
    for a in qs:
        p = probes[a["id"]]; rc = m.choose(a["question"])
        notes = "".join(m.rooms.moments[i].text + "\n" for i in m.rooms.rooms[rc.room].members) + \
                "".join(m.rooms.moments[i].text + "\n" for i in rc.closest)
        for k, w in WORDINGS.items():
            system = f"{w}\n\nNotes:\n{notes}End of notes.\nToday is {today:%A %d %B %Y}."
            ids = reader.tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": a["question"]}],
                                                 add_generation_prompt=True, enable_thinking=False)
            t = reader.generate(ids, max_tokens=60).text
            g = grader({"probe": p, "question": a["question"]}, t)
            s = score[k].setdefault(a["family"], [0, 0]); s[1] += 1; s[0] += g["right"]
    print(cut, {k: {f: f"{v[0]}/{v[1]}" for f, v in d.items()} for k, d in score.items()}, flush=True)
