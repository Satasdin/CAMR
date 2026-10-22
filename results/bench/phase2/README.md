# Phase 2: closing the gaps the engine bench found

> **Correction (2026-10-22, re-scored).** The tables below used a first scoring rule that counted a needed fact as
> reached when any note of its turn was admitted. With `compress = sentences` that is wrong: compression keeps a
> note's sentences that share words with the question, and the sentence holding the answer often shares none ("I
> upgraded to 500 Mbps" vs "What speed is my new internet plan?"). The reader bench found it (Kimi K3 recall
> fell). Re-scored so that the answer must survive in the rendered context (`rescore/README.md`), compression
> *loses*: answerable pass 48% at 384 tokens against 59% for whole notes, and 77% against 80% on the questions
> whose gold answer is in the turn verbatim. The step-4 gains (A2 52%, A3 81%, A4 67%) are not real. Whole notes
> win: 384 tokens is the most efficient (0.151 passes per 100 tokens), 512 adds 4 points (63%), 768 adds 14 (73%).
> Compression was chosen under a rule that did not check whether the answer survived, and was reversed: CAMR
> Personal now uses whole notes at 512 tokens, with tightened profile notes (`phase2b` in the table below).

## Before and after (answer must survive)

| | Ability | baseline | phase2-compressed | phase2b |
|---|---|---|---|---|
| A1 | recall one taught fact among many | 84% (155) | 81% | 86% |
| A2 | join two facts | 28% (40) | 12% | 35% |
| A3 | knowledge update | 65% (43) | 51% | 70% |
| A4 | temporal | 40% (42) | 24% | 48% |
| A5 | counting | 33% (3) | 67% | 67% |
| A6 | implicit preference | 67% (33) | 82% | 76% |
| A7 | abstention | 15% (34) | 26% | 26% |
| A8 | forget and privacy | 88% (16) | 100% | 100% |
| A9 | scale | 67% (3) | 100% | 100% |
| A10 | do no harm (engine proxy) | 62% (82) | 67% | 67% |

| Run | Mean context tokens | Distractor share | Profile lines (questions reached) |
|---|---|---|---|
| baseline: the read path before Phase 2 | 316 | 73% | 0 (0 of 260 LongMemEval questions) |
| phase2-compressed: Phase 2 as first shipped: compression at 384 tokens (reversed) | 409 | 83% | 570 (260 of 260 LongMemEval questions) |
| phase2b: CAMR Personal now: whole notes at 512 tokens, tightened profile notes | 472 | 81% | 219 (155 of 260 LongMemEval questions) |

## Step by step, first scoring rule (history)

Kept as the record of how each change was measured. This rule counted a needed fact once a note of its turn reached the context; it overstates compression (step 4 and step 5) badly and whole-note rows a little (an answer can sit in another 120-token chunk of the turn). The headline above and rescore/README.md use the answer-survives rule.

Each step turns on one more change (a MemoryConfig flag, off by default) and re-runs the whole engine bench: 260 LongMemEval questions, the CAMR probes, the needle stores at 1k/10k/100k, the forget and privacy checks. Pass rates per ability (n in the baseline column).

| | Ability | baseline | step0-before | step1-dates | step2-profile | step3-aggregate | step4-compress | step5-slot-v1 | step5-final |
|---|---|---|---|---|---|---|---|---|---|
| A1 | recall one taught fact among many | 88% (155) | 88% | 88% | 88% | 88% | 91% | 87% | 91% |
| A2 | join two facts | 28% (40) | 28% | 28% | 32% | 38% | 52% | 38% | 52% |
| A3 | knowledge update | 65% (43) | 65% | 70% | 70% | 70% | 81% | 70% | 81% |
| A4 | temporal | 40% (42) | 40% | 45% | 45% | 48% | 67% | 48% | 67% |
| A5 | counting | 33% (3) | 33% | 33% | 33% | 67% | 67% | 67% | 67% |
| A6 | implicit preference | 70% (33) | 70% | 70% | 82% | 82% | 85% | 79% | 85% |
| A7 | abstention | 15% (34) | 15% | 15% | 12% | 12% | 12% | 29% | 26% |
| A8 | forget and privacy | 88% (16) | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| A9 | scale | 67% (3) | 33% | 67% | 67% | 67% | 100% | 100% | 100% |
| A10 | do no harm (engine proxy) | 62% (82) | 62% | 62% | 61% | 61% | 61% | 68% | 67% |

Steps: **baseline** committed baseline (bench/engine-bench); **step0-before** Phase 2 code, every new flag off (+ forget fix); **step1-dates** + dated_context, time_filter; **step2-profile** + profile, entity_gate_skip_time; **step3-aggregate** + aggregate; **step4-compress** + compress (sentences, 384 tokens), chosen below; **step5-slot-v1** step 3 + slot_gate as first written (dropped); **step5-final** step 4 + slot_gate = CAMR Personal's configuration.

| Step | Mean context tokens | Distractor share | Retrieval ms p50 / p95 | Gate precision / specificity |
|---|---|---|---|---|
| baseline | 248 | 60% | 19.4 / 102.8 | 91% / 62% |
| step0-before | 248 | 60% | 33.0 / 947.8 | 91% / 62% |
| step1-dates | 248 | 60% | 29.5 / 95.3 | 91% / 62% |
| step2-profile | 305 | 79% | 10.6 / 62.7 | 91% / 61% |
| step3-aggregate | 320 | 79% | 11.3 / 302.1 | 91% / 61% |
| step4-compress | 328 | 81% | 10.4 / 63.3 | 91% / 61% |
| step5-slot-v1 | 313 | 79% | 11.7 / 84.7 | 92% / 68% |
| step5-final | 324 | 80% | 11.3 / 66.8 | 92% / 67% |

## Context budget

LongMemEval and needle questions of A1, A2, A3, A4, A6 (answerable), on top of step 3. Prefill time grows with the context, so the choice is made by pass rate per context token among variants that stay at or under 512 tokens of context on average.

| Variant | Context | n | Pass (95% CI) | Mean context tokens | Pass per 100 tokens | A1 | A2 | A3 | A4 | A6 |
|---|---|---|---|---|---|---|---|---|---|---|
| step3-aggregate | 384 tokens, whole notes | 305 | 72% (67–77) | 353 | 0.21 | 88% | 38% | 68% | 45% | 80% |
| budget-512 | 512 tokens, whole notes | 305 | 76% (71–80) | 451 | 0.17 | 90% | 48% | 72% | 48% | 83% |
| budget-768 | 768 tokens, whole notes | 305 | 84% (79–87) | 643 | 0.13 | 94% | 62% | 82% | 65% | 87% |
| compress-384 | 384 tokens, compressed notes | 305 | 80% (76–84) | 361 | 0.22 | 91% | 52% | 80% | 65% | 83% |
| compress-512 | 512 tokens, compressed notes | 305 | 84% (80–88) | 450 | 0.19 | 94% | 62% | 82% | 68% | 87% |
| chunk60-384 | 384 tokens, 60-token chunks | 80 | 74% (63–82) | 406 | 0.18 | 84% | 50% | 75% | 75% | – |
| step3-aggregate@slice | 384 tokens, whole notes (same slice as chunk60) | 80 | 64% (53–73) | 386 | 0.17 | 81% | 31% | 75% | 50% | – |

## What changed, and what was decided

Every change is a `MemoryConfig` flag that is off by default; only CAMR Personal (`camr/app/assistant.py`)
turns them on, so the research configurations and their replays are untouched (`reproduce.py`, below).

| Flag | In the app | What it does | Where |
|---|---|---|---|
| `dated_context` | on | each admitted note shows its date (`[2026-10-13] The user said: …`, from the chat line, else the day it was stored); notes are listed oldest first; the prompt says "Today is …" and "when notes disagree, the newest is right" | `engine._render`, `budgeter.pack(render, order)`, `CHAT_PROMPT` |
| `time_filter` | on | a question about the past that names a period ("last week", "this month", "in March", "two weeks ago", "last Thursday") drops notes *said before* the period began | `memory/timeframe.py` |
| `entity_gate_skip_time` | on | days, months and "today/tomorrow" are not names for the entity gate ("dinner place for Friday") | `entities.question_entities(skip_time=)` |
| `profile` | on | lasting traits the user states ("I am vegetarian", "milk upsets my stomach", "I avoid flying", "I prefer Airbnb") are also kept as profile notes (own note population); the best of them are offered to every question within 64 tokens, whatever the gates decide; forgetting a note forgets the profile notes taken from it | `memory/profile.py`, `engine._ingest_profile`, `engine._with_profile`, `Assistant._delete_source` |
| `aggregate` | on | "how many times / how often / in total / list all / every time": k 100, keyword hits on the event words count even below the margin, one short dated line per event, budget 1024 for that question | `engine.recall`, `_first_clause` |
| `slot_gate` | on | a first-person question asking for a specific thing ("my passport number", "my brother's wedding", "the code for my bike lock") abstains unless an eligible note mentions that thing (owner and thing for "X's Y"; any of the thing's words otherwise); profile notes are exempt | `entities.personal_slots`, `engine._slot_gate` |
| `token_budget` | 512 | the context budget: whole notes, 512 tokens (was 384) | `Assistant(token_budget=512)` |
| `compress = sentences` | **off** | an admitted note keeps only its sentences sharing the most words with the question. Kept in the code for the record; reversed (below) | `engine._relevant_sentences` |

Decisions made on the bench:

* **Compression was chosen, then reversed.** It was chosen on a scoring rule that counted a needed fact as
  reached once a note of its turn was in the context, without checking that the answer was still in it. Under
  that rule compression at 384 tokens looked best (76% of answerable questions, against 67% for whole notes).
  The reader bench showed answers going missing (Kimi K3 recall fell), and the bench was re-scored so that the
  answer must survive in what the reader sees (`rescore/`): compression cut the answer of 105 needed facts and
  fell to 48%, below whole notes (59% at 384, 63% at 512, 73% at 768). CAMR Personal now uses whole notes at
  512 tokens (the user's choice: +4 points over 384 for about 110 more tokens; 768 gains 10 more at about 220
  more).
* **Profile notes, tightened.** The first extractor took likes, plans and recent pursuits as well as traits ("I'm
  trying to …", "I love the idea!", "I've been using …", questions and requests): on LongMemEval it put 570
  profile lines into all 260 contexts, mostly passing remarks. It now keeps only statements of lasting traits
  (diet, allergy, intolerance, fear, standing preferences, "I always/never <habit>", favourites stated as
  such, who the user is), never a question, a request, a plan, a reaction or an exclamation; tests use the bad
  lines as negatives. On the same questions: 219 lines in 155 of 260 contexts. Profile notes are still offered
  always, not by similarity: BGE puts "Can you suggest a dinner place for Friday?" at 0.37 from "I am vegetarian
  …" and unrelated pairs higher (0.45).
* **Time filter, three fixes before it was kept.** As first written it cost A2 and A6: "a show for *tonight*" and
  "my bedroom *this weekend*" are plans, not periods, and a note said after the period can tell of it ("last
  Thursday I earned …"). Now only past-tense questions name a period, plans never do, and the window runs from
  the period's start to today; "last Thursday" reaches back a week (people use it for either of the last two).
* **The slot gate, second version.** The first version demanded every word of the slot and read "kitchen's
  becoming" as a possessive (it cost two A1 questions and one A6). The kept version asks for the owner and the
  thing of "X's Y", any word of the thing otherwise, and knows -ing nouns (wedding, meeting).
* **A10** ("nothing admitted for a question memory has nothing for") judges the ranked notes only; the profile
  lane is reported apart (`profile_tokens`) and counts in the distractor share.

## Targets (answer-survives rule; CAMR Personal as it now is, `phase2b`)

| Ability | Target | Before | After | |
|---|---|---|---|---|
| A3 knowledge update | ≥ 85% | 65% | 70% | not met: every CAMR update probe passes; LongMemEval updates miss on margin and budget |
| A4 temporal | ≥ 70% | 40% | 48% | not met: the CAMR time probes pass; LongMemEval temporal questions join several dated facts and still run out of budget |
| A5 counting | 30-event probe | fails | passes | met (100 events do not fit 1024 tokens) |
| A6 implicit preference | ≥ 85% | 67% | 76% | not met under the answer rule: the CAMR preference probes pass; LongMemEval preference questions miss on budget |
| A7 abstention | ≥ 50%, A1 and A6 not lower | 15% | 26% | not met: most LongMemEval abstention questions ask about an activity ("How many times did I bake egg tarts?"), which a slot gate cannot see |

## Checks

* `scripts/reproduce.py --only tests,lookup-dev,verified-dev,verified-test,verified-heldout,governor,math`: see
  `reproduce.txt`.
* Latency: steps 0 and 1 ran while the machine was overloaded (load average above 100), so their retrieval
  times are not comparable; later runs were made on a quieter machine, phase2b with a reader bench running.
* A8 is 16 of 16 from step 0 on: fix/app-issues (df6b713, FTS5 secure-delete) was merged before the runs.
* Contexts for the reader bench: `results/bench/contexts_phase2.jsonl` (compressed, the first Phase 2 read
  path, kept as its record) and `results/bench/contexts_phase2b.jsonl` (CAMR Personal as it now is).
