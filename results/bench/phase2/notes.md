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
