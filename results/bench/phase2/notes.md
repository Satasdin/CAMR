## What changed, and what was decided

Every change is a `MemoryConfig` flag that is off by default; only CAMR Personal (`camr/app/assistant.py`)
turns them on, so the research configurations and their replays are untouched (`reproduce.py`, below).

| Flag (on in the app) | What it does | Where |
|---|---|---|
| `dated_context` | each admitted note shows its date (`[2026-10-13] The user said: …`, from the chat line, else the day it was stored); notes are listed oldest first; the prompt says "Today is …" and "when notes disagree, the newest is right" | `engine._render`, `budgeter.pack(render, order)`, `CHAT_PROMPT` |
| `time_filter` | a question about the past that names a period ("last week", "this month", "in March", "two weeks ago", "last Thursday") drops notes *said before* the period began | `memory/timeframe.py` |
| `entity_gate_skip_time` | days, months and "today/tomorrow" are not names for the entity gate ("dinner place for Friday") | `entities.question_entities(skip_time=)` |
| `profile` | lasting traits the user states ("I am vegetarian", "milk upsets my stomach", "I avoid flying") are also kept as profile notes (own note population); the best of them are offered to every question within 64 tokens, whatever the gates decide; forgetting a note forgets the profile notes taken from it | `memory/profile.py`, `engine._ingest_profile`, `engine._with_profile`, `Assistant._delete_source` |
| `aggregate` | "how many times / how often / in total / list all / every time": k 100, keyword hits on the event words count even below the margin, one short dated line per event, budget 1024 for that question | `engine.recall`, `_first_clause` |
| `compress = sentences` | an admitted note keeps only its (at most two) sentences sharing the most words with the question, so more notes fit the 384 tokens | `engine._relevant_sentences` |
| `slot_gate` | a first-person question asking for a specific thing ("my passport number", "my brother's wedding", "the code for my bike lock") abstains unless an eligible note mentions that thing (owner and thing for "X's Y"; any of the thing's words otherwise); profile notes are exempt | `entities.personal_slots`, `engine._slot_gate` |

Decisions made on the bench:

* **Time filter, three fixes before it was kept.** As first written it cost A2 and A6: "a show for *tonight*" and
  "my bedroom *this weekend*" are plans, not periods, and a note said after the period can tell of it ("last
  Thursday I earned …"). Now only past-tense questions name a period, plans never do, and the window runs from
  the period's start to today. "Last Thursday" also reaches back a week, since people use it for either of the
  last two Thursdays (LongMemEval's own SaveMart question does). With that, step 1 lost nothing.
* **Profile notes are offered always, not by similarity.** BGE puts "Can you suggest a dinner place for Friday?"
  at 0.37 from "I am vegetarian …" and unrelated pairs higher (0.45), so a similarity floor cannot pick them.
  The lane costs about 60 tokens on every question; A10 ("nothing admitted for a question memory has nothing
  for") judges the ranked notes only and reports the profile tokens apart (`profile_tokens`), and the distractor
  share counts them.
* **The budget.** Compression at 384 tokens: best pass rate per context token of the variants at or under 512
  (curve above), and no ability lower than without it. 60-token chunks were measured on a stratified 80-question
  slice (they need new vectors): 74% against 80% for compression on the same slice.
* **The slot gate, second version.** The first version demanded every word of the slot and read "kitchen's
  becoming" as a possessive: it cost two A1 questions and one A6 (`step5-slot-v1`). The kept version asks for the
  owner and the thing of "X's Y", any word of the thing otherwise, and knows -ing nouns (wedding, meeting): no
  losses.

## Targets

| Ability | Target | Before | After | |
|---|---|---|---|---|
| A3 knowledge update | ≥ 85% | 65% | 81% | not met: every CAMR update probe passes; LongMemEval updates 80% (misses: below margin 4, entity gate 2, budget 2) |
| A4 temporal | ≥ 70% | 40% | 67% | not met by one or two questions: LongMemEval temporal 65%, mostly multi-fact questions still over budget |
| A5 counting | 30-event probe | fails | passes | met (100 events still do not fit 1024 tokens) |
| A6 implicit preference | ≥ 85% | 70% | 85% | met |
| A7 abstention | ≥ 50%, A1 and A6 not lower | 15% | 26% | not met; A1 and A6 not lower. Most LongMemEval abstention questions ask about an activity rather than "my X's attribute" ("How many times did I bake egg tarts?"), which a slot gate cannot see |

## Checks

* `scripts/reproduce.py --only tests,lookup-dev,verified-dev,verified-test,verified-heldout,governor,math`:
  lookup-dev, verified-dev, verified-test, verified-heldout, governor and math replay identically. The test
  check first failed on two figure tests (matplotlib could not open a font while other jobs rebuilt its cache
  under a load average near 100); both pass alone, and the re-run result is in `reproduce.txt`.
* Latency: steps 0 and 1 ran while the machine was overloaded (load average above 100, a VM and the reader
  bench running), so their retrieval times are not comparable; from step 2 on the machine was quiet. At the end:
  p50 / p95 7 / 11 ms at 1k notes, 13 / 15 ms at 10k, 66 / 95 ms at 100k (baseline 9 / 11, 23 / 36, 99 / 165).
* A8 rises to 16 of 16 from step 0 on: fix/app-issues (df6b713, FTS5 secure-delete) was merged before the runs.
* `results/bench/contexts_phase2.jsonl`: the exact context of every LongMemEval question and CAMR probe on this
  read path, for the reader bench (`contexts_baseline.jsonl` is on bench/engine-bench).
