"""Tricky questions: the Long Haul's own facts asked the way people ask, written by Claude, graded by the world.

    .venv/bin/python scripts/tricky.py make --haul ../work/haul/s1-16m --cut 16M --out ../work/haul/s1-16m-tricky
    .venv/bin/python -m camr_engine.bench.desk --memory <snap> --haul ../work/haul/s1-16m-tricky --cut 16M \
        --per-family 100 --variant ...
    .venv/bin/python scripts/tricky.py claude --memory <snap> --haul ../work/haul/s1-16m-tricky --cut 16M

``make`` takes ``--per`` probes from each of five families (fact, changed, lookalike, never, two_hop) that the haul's
exam never asked at ``--cut`` (the desk's own sample, per family 10, seed 0, is left out), and asks Claude to write
three new forms of each, so every base is asked four ways:

- plain: the question as the world wrote it (the control);
- reworded: the same question with every word but the names changed (a finder that matches words must cope);
- premise: a question that takes a wrong value as fact (another value from the probe's own pool, the lookalike's
  confusable one, the value it held before it changed, or, for a never-said fact, a made-up one); the answer has to
  correct it;
- buried: the question in the middle of a chatty message about something else.

Claude writes words only. The answer and the grader are the probe's own, so every gold comes from the world, and the
rule grader (camr_engine.bench.haul.grade) marks every contender the same way. A form that names the answer is
refused and written again.

``claude`` asks Claude the same questions with exactly what CAMR's accurate reader put in front of the 4B (its notes as
words, the date and the question), so the record shows how much a stronger reader gets from the same memory.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAMILIES = ("fact", "changed", "lookalike", "never", "two_hop")
FORMS = ("plain", "reworded", "premise", "buried")
WRITER = "claude-opus-5-5"
READER = "claude-sonnet-5-5"
STOP_AT_USD = 56.0  # this script stops before the ledger reaches it (the ledger's own cap is 60)

SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "string"}, "wrong_value": {"type": "string"},
                                     "reworded": {"type": "string"},
                                     "premise": {"type": "string"}, "buried": {"type": "string"}},
    "required": ["id", "wrong_value", "reworded", "premise", "buried"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}

BRIEF = """You write test questions for a memory system. It holds a long chat history between a developer and an \
assistant about running a business; the questions check what it remembers.

For each item you get the original question, its correct answer (for your understanding only: never write it), and a \
WRONG value. When the wrong value is null, make one up: a plausible value of the same kind as the correct answer (a \
day for a day, an amount for an amount, a name for a name) that is not the correct answer. Return the wrong value you \
used in "wrong_value". Write three new forms of the same question. Each must ask for exactly the same information, so the same \
answer is still correct:

1. reworded: the same question in different words. Keep every proper name (people, places, businesses, products, \
models) exactly as written; change every other content word for a synonym or a paraphrase, and change the sentence's \
shape. Casual, the way a busy person types.
2. premise: a question that wrongly takes the WRONG value as already settled fact, without asking whether it is true \
(no "is it", "did they", "or"), while still asking for the same thing as the original, so the true answer to it \
is the correct answer. A careful answer must correct the premise and give the real value. Example: original "Which \
laptop does Victor use?", wrong value "ThinkPad T14" -> "Remind me why Victor went for the ThinkPad T14 as his \
laptop?" When the correct answer is that the history never said, write the WRONG value as if it had been said.
3. buried: a natural, chatty message of 50 to 100 words from the developer that is mostly about something routine and \
unrelated (a late delivery, the printer, lunch, a meeting moving), with the question asked once in the middle in your \
own words. No other question. Mention no names, numbers, dates or values except those in the original question.

When the original asks about the current state ("now", "these days", "currently"), every form keeps that sense.
Never write the correct answer, or any part of it, in any form. Reply with JSON only."""


def ledger_spent() -> float:
    from camr_engine.bench.claude import Ledger

    return Ledger().spent()


def guard() -> None:
    spent = ledger_spent()
    if spent >= STOP_AT_USD:
        raise SystemExit(f"Claude spend is ${spent:.2f}; this script stops at ${STOP_AT_USD:.2f}")


def wrong_value(p: dict, raw: dict, rng: random.Random) -> str | None:
    """A wrong value of the same kind for the premise form, or None when Claude should make one up (a never-said
    fact whose pool is a placeholder, a two-hop answer with no pool of its own)."""
    g = p["grader"]
    right = {a.lower() for a in g.get("accept", [])} | {str(p.get("answer", "")).lower()}
    timeline = raw.get(p["id"], {}).get("grader", {})
    if timeline.get("type") == "timeline":  # the value it held just before the current one
        vals = [v["value"] for v in timeline["values"] if v["value"].lower() not in right]
        return vals[-1] if vals else None
    if g["type"] == "never":
        pool = [v for v in g.get("pool", []) if not re.search(r"[#{}]", v)]
        return rng.choice(pool) if pool else None
    if g.get("reject"):
        return g["reject"][0]
    if g.get("others"):
        return rng.choice(g["others"])
    return None


def names_answer(text: str, p: dict) -> bool:
    if p["grader"]["type"] == "never":
        return False
    words = [p.get("answer", "")] + list(p["grader"].get("accept", []))
    return any(w and re.search(rf"(?<!\w){re.escape(w.lower())}(?!\w)", text.lower()) for w in words)


def make(a) -> int:
    from camr_engine.bench.claude import Claude
    from camr_engine.bench.haul.sample import askable
    from camr_engine.bench.haul.script import load_probes
    from camr_engine.bench.longhaul import CUTS, checkpoints

    probes = load_probes(a.haul)
    _, cps = checkpoints(a.haul, {a.cut: CUTS[a.cut]})
    asked = {q["id"] for q in cps[0]["questions"]}
    ready = [p for p in askable(probes, cps[0]["tokens"]) if p["id"] not in asked]
    rng = random.Random("tricky-1")
    raw = {p["id"]: p for p in probes}
    bases = []
    for fam in FAMILIES:
        cands = sorted((p for p in ready if p["family"] == fam
                        and (fam != "changed" or (p["id"].endswith("-now") and not p["grader"].get("on_day")))),
                       key=lambda p: p["id"])
        bases += rng.sample(cands, min(a.per, len(cands)))
    for p in bases:
        p["_wrong"] = wrong_value(p, raw, rng)
    claude = Claude()
    written, calls = {}, []
    for fam in FAMILIES:
        todo = [p for p in bases if p["family"] == fam]
        for attempt in range(3):
            todo = [p for p in todo if p["id"] not in written]
            if not todo:
                break
            guard()
            items = [{"id": p["id"], "question": p["ask"], "correct_answer": p["answer"], "wrong_value": p["_wrong"]}
                     for p in todo]
            c = claude.call(WRITER, [{"role": "user", "content": json.dumps({"items": items}, indent=1)}],
                            system=BRIEF, max_tokens=16000, purpose=f"tricky-write-{fam}",
                            output_config={"format": {"type": "json_schema", "schema": SCHEMA}})
            calls.append(c.as_dict())
            for it in json.loads(c.text)["items"]:
                p = next((q for q in todo if q["id"] == it["id"]), None)
                if p is None:
                    continue
                bad = [f for f in ("reworded", "premise", "buried") if names_answer(it[f], p)]
                wrong = p["_wrong"] or it["wrong_value"]
                if names_answer(wrong, p) or wrong.lower() in str(p["answer"]).lower():
                    bad.append("wrong-value-is-right")
                if wrong.lower() not in it["premise"].lower():
                    bad.append("premise-without-wrong-value")
                if bad:
                    print(f"{p['id']}: rewritten ({', '.join(bad)})", flush=True)
                    continue
                it["wrong_value"] = wrong
                written[p["id"]] = it
            print(f"{fam}: {sum(1 for p in bases if p['family'] == fam and p['id'] in written)} written, "
                  f"${sum(x['cost_usd'] for x in calls):.2f} so far", flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    out = []
    for p in bases:
        if p["id"] not in written:
            print(f"{p['id']}: left out (never written cleanly)")
            continue
        w = written[p["id"]]
        for form in FORMS:
            q = {k: v for k, v in p.items() if not k.startswith("_")}
            q.update(id=f"{p['id']}.{form}", family=f"{p['family']}.{form}", base=p["id"], form=form,
                     ask=p["ask"] if form == "plain" else w[form], sample=False)
            if form == "premise":
                q["premise"] = w["wrong_value"]
            out.append(q)
    (a.out / "probes.jsonl").write_text("".join(json.dumps(q) + "\n" for q in out))
    script = a.out / "script.jsonl"
    if not script.exists():
        script.symlink_to((a.haul / "script.jsonl").resolve())
    m = json.loads((a.haul / "manifest.json").read_text())
    m["tricky"] = {"from": str(a.haul), "cut": a.cut, "per": a.per, "families": FAMILIES, "forms": FORMS,
                   "bases": len(out) // len(FORMS), "writer": WRITER, "seed": "tricky-1",
                   "cost_usd": round(sum(x["cost_usd"] for x in calls), 4), "calls": calls}
    (a.out / "manifest.json").write_text(json.dumps(m, indent=1))
    print(f"{len(out)} questions ({len(out) // len(FORMS)} bases x {len(FORMS)} forms) in {a.out}")
    return 0


def split_chat(text: str) -> tuple[str, str]:
    """The system and user parts of a Qwen chat as the 4B read it."""
    sys_m = re.search(r"<\|im_start\|>system\n(.*?)<\|im_end\|>", text, re.S)
    user_m = re.search(r"<\|im_start\|>user\n(.*?)<\|im_end\|>", text, re.S)
    return (sys_m.group(1) if sys_m else ""), (user_m.group(1) if user_m else text)


def ask_claude(a) -> int:
    from camr_engine.bench.claude import Claude
    from camr_engine.bench.contender import ask_one, environment
    from camr_engine.bench.desk import attach, configure, parse_variant
    from camr_engine.bench.longhaul import CUTS, checkpoints, grader

    _, cps = checkpoints(a.haul, {a.cut: CUTS[a.cut]}, per_family=1000)
    questions = cps[0]["questions"]
    if a.limit:
        questions = questions[:a.limit]
    kind, settings = parse_variant(a.variant)
    engine = attach(a.model, a.memory)
    configure(engine, settings)
    m = engine.memory
    seen: dict = {}
    real = m._generate

    def capture(said, todo, cache, max_tokens):
        head = m.notebook.header
        seen["kept_notes"] = int(cache[0].offset) - len(head) if cache else 0
        seen["text"] = m.reader.tok.decode(list(head) + list(todo))
        return real(said, todo, cache, max_tokens)

    m._generate = capture
    claude = Claude()
    rows, t0 = [], time.time()
    try:
        for q in questions:
            guard()
            seen.clear()
            local = ask_one(engine, q, grader, history_tokens=cps[0]["tokens"])
            system, user = split_chat(seen.get("text", ""))
            c = claude.call(READER, [{"role": "user", "content": user}], system=system, max_tokens=4000,
                            purpose="tricky-read", prompt_tokens=len(seen.get("text", "")) // 3 + 50, cache=False)
            g = grader(q, c.text)
            rows.append({"id": q["id"], "family": q["family"], "question": q["question"], "expected": q["expected"],
                         "qwen": {"answer": local["answer"], "verdict": local["verdict"], "right": local["right"]},
                         "claude": {"answer": c.text, "verdict": g["verdict"], "right": g["right"],
                                    "call": c.as_dict()},
                         "kept_notes": seen.get("kept_notes", 0), "context_chars": len(seen.get("text", ""))})
            if len(rows) % 20 == 0:
                print(f"{len(rows)}/{len(questions)} qwen {sum(r['qwen']['right'] or 0 for r in rows)} "
                      f"claude {sum(r['claude']['right'] or 0 for r in rows)} "
                      f"${sum(r['claude']['call']['cost_usd'] for r in rows):.2f}", flush=True)
    finally:
        engine.close()
    rec = {"kind": "tricky-claude-reader", "variant": a.variant, "reader": READER, "model": a.model,
           "memory": str(a.memory), "haul": str(a.haul), "cut": a.cut, "environment": environment(),
           "seconds": round(time.time() - t0, 1), "cost_usd": round(sum(r["claude"]["call"]["cost_usd"] for r in rows), 4),
           "answers": rows}
    a.records.mkdir(parents=True, exist_ok=True)
    path = a.records / f"{time.strftime('%H%M%S')}-tricky-claude-reader.json"
    path.write_text(json.dumps(rec, indent=1))
    print(path)
    print(f"qwen {sum(r['qwen']['right'] or 0 for r in rows)}/{len(rows)}, "
          f"claude {sum(r['claude']['right'] or 0 for r in rows)}/{len(rows)}, ${rec['cost_usd']:.2f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make")
    mk.add_argument("--haul", type=Path, required=True)
    mk.add_argument("--cut", default="16M")
    mk.add_argument("--out", type=Path, required=True)
    mk.add_argument("--per", type=int, default=12)
    cl = sub.add_parser("claude")
    cl.add_argument("--memory", type=Path, required=True)
    cl.add_argument("--haul", type=Path, required=True)
    cl.add_argument("--cut", default="16M")
    cl.add_argument("--model", default="qwen3-4b")
    cl.add_argument("--variant", default="camr:finder=words,closest=6,asleep=words,follow=3,latest=1")
    cl.add_argument("--limit", type=int)
    cl.add_argument("--records", type=Path, default=Path("records/bench") / time.strftime("%Y-%m-%d"))
    a = ap.parse_args()
    return make(a) if a.cmd == "make" else ask_claude(a)


if __name__ == "__main__":
    raise SystemExit(main())
