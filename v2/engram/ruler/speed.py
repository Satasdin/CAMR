"""How long until the first word, by how much memory is on the desk: engram's notes against reading the same words.

For each size, the first moments of a development life (seed 0) are remembered into one room until it holds that
many words. The same question is then answered as engram answers it, from the room's notes (fetched from the SSD,
bypassing RAM) and its closest moments as words, and from the same desk read entirely as words. Each point is the
median of several tries. Sizes beyond the usual allowance are measured on purpose.
"""

from __future__ import annotations

import json
import shutil
import statistics
import time
from pathlib import Path

from engram.ruler.harness import environment
from engram.ruler.life import build

SIZES = (250, 500, 1000, 2000, 3000)  # words in the room on the desk
TRIES = 5


def measure(reader, embedder, workdir: Path, persona: str = "student", out: Path | None = None, progress=print):
    from engram.memory import Memory

    life = build(persona, 0)
    moments = [(d.index, t) for d in life.days for t in d.dated()]
    question = next(q for q in life.questions if q.kind == "single").text
    points = []
    for size in SIZES:
        shutil.rmtree(workdir, ignore_errors=True)
        memory = Memory(reader, embedder, workdir, room_tokens=10**6, join=-1.0, allowance=2**40)  # one room
        words = 0
        for day, text in moments:
            if words >= size:
                break
            memory.remember(text, day)
            words += len(text.split())
        head, rest = memory.prompt(life.days[-1].date, question)
        reader.generate(head + rest)  # warm the model
        notes_s, fetch_s, words_s = [], [], []
        for _ in range(TRIES):
            t = time.perf_counter()
            rec = memory.recall(question)
            ids = memory.words(rec.closest) + rest
            before = time.perf_counter() - t
            notes_s.append(before + reader.generate(ids, cache=rec.desk).ttft_s)
            fetch_s.append(rec.seconds["fetch"])
            t = time.perf_counter()
            rec = memory.choose(question)
            ids = head + memory.room_words(rec.room) + memory.words(rec.closest) + rest
            before = time.perf_counter() - t
            words_s.append(before + reader.generate(ids).ttft_s)
        p = {"words": words, "tokens": rec.tokens, "mb": round(rec.bytes / 1e6),
             "fetch_s": round(statistics.median(fetch_s), 3),
             "notes_first_word_s": round(statistics.median(notes_s), 3),
             "words_first_word_s": round(statistics.median(words_s), 3)}
        p["times_sooner"] = round(p["words_first_word_s"] / p["notes_first_word_s"], 1)
        points.append(p)
        progress(f"{words:5d} words ({p['tokens']} tokens, {p['mb']} MB): notes {p['notes_first_word_s']} s "
                 f"(SSD {p['fetch_s']} s), words {p['words_first_word_s']} s, {p['times_sooner']}x sooner")
        memory.close()
    shutil.rmtree(workdir, ignore_errors=True)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"kind": "speed", "persona": persona, "seed": 0, "question": question,
                                   "tries": TRIES, "environment": environment(), "points": points}, indent=1))
    return points
