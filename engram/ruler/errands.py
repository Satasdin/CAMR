"""Errands on a life: every quiz question as a task with tools, done once on the life's last day.

The agent use case, measured the same way for every contender: the same reader, the same tools, the same task
instructions after the notes. Only the memory differs: none (bare), the old CAMR's packed notes, or engram's desk.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import time
from collections import Counter
from pathlib import Path

from engram.agent import THEN, TOOLS, act, done, grade, parse, tasks
from engram.ruler.contenders import SYSTEM, today_text
from engram.ruler.harness import RECORDS, environment


def run(life, name: str, reader, embedder, work: Path, records: Path = RECORDS, progress=print, suffix: str = "") -> Path:
    day = life.days[-1]
    shutil.rmtree(work, ignore_errors=True)
    t0 = time.perf_counter()
    if name == "engram":
        from engram.memory import Memory

        memory = Memory(reader, embedder, work)
        for d in life.days:
            for text in d.dated():
                memory.remember(text, d.index)

        def do(task_text):
            tool, args, reply = act(memory, task_text, day.date)
            return tool, args, reply
    else:
        notes_for = lambda q: "(none)"
        if name == "camr2-words":
            from engram.ruler.contenders import CamrWords

            words = CamrWords(reader, embedder, work)
            for d in life.days:
                words.observe(d)
            notes_for = words.notes_for
        if name == "camr":
            from engram.ruler.__main__ import CAMR_MIN_SIMILARITY
            from engram.ruler.contenders import CamrText

            camr = CamrText(reader, embedder, work, CAMR_MIN_SIMILARITY)
            for d in life.days:
                camr.observe(d)
            camr.begin_quiz(day.date)
            notes_for = camr.notes_for

        def do(task_text):
            t = time.perf_counter()
            system = SYSTEM.format(today=today_text(day.date), notes=notes_for(task_text)) + "\n\n" + THEN
            before = time.perf_counter() - t
            reply = reader.generate(reader.chat_ids(system, task_text, TOOLS), max_tokens=120)
            reply.ttft_s += before
            tool, args = parse("".join(reply.pieces))
            return tool, args, reply
    observe_s = time.perf_counter() - t0
    rows, verdicts = [], Counter()
    for t in tasks(life):
        tool, args, reply = do(t.text)
        v = grade(t, tool, args, day.index)
        right = t.question.answer_on(day.index)
        verdicts[v] += 1
        rows.append({"qid": t.question.qid, "kind": t.question.kind, "task": t.text, "expected_tool": t.tool,
                     "expected": right[0] if right else None, "tool": tool, "args": args, "said": done(tool, args),
                     "raw": "".join(reply.pieces),
                     "verdict": v, "ttft_s": round(reply.ttft_s, 4)})
    told = sum(r["expected"] is not None for r in rows)
    waits = sorted(r["ttft_s"] for r in rows)
    summary = {"tasks": len(rows), "told": told, "knows": verdicts["right"], "untold": len(rows) - told,
               "honest": verdicts["right_abstain"], "false_memories": verdicts["false_memory"],
               "stale": verdicts["stale"], "missed": verdicts["missed"], "wrong": verdicts["wrong"],
               "asked": sum(r["tool"] == "ask_user" for r in rows), "no_tool": sum(r["tool"] is None for r in rows),
               "wait_median_s": waits[len(waits) // 2] if waits else None}
    started = dt.datetime.now()
    name = name + suffix
    out = records / started.strftime("%Y-%m-%d") / f"{started.strftime('%H%M%S')}-{life.persona}-s{life.seed}-errands-{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"kind": "errands", "persona": life.persona, "seed": life.seed, "contender": name,
                               "day": day.index, "observe_s": round(observe_s, 1), "environment": environment(),
                               "summary": summary, "tasks": rows}, indent=1))
    progress(f"{life.persona} s{life.seed} errands {name}: knows {summary['knows']}/{told}, honest "
             f"{summary['honest']}/{summary['untold']}, false memories {summary['false_memories']}, asked "
             f"{summary['asked']}, wait {summary['wait_median_s']} s")
    if name.startswith("engram"):
        memory.close()
    elif name.startswith("camr2-words"):
        words.close()
    elif name.startswith("camr"):
        camr.close()
    return out
