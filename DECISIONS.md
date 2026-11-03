# Decisions

Technical calls made while building engram, each with its reason. Ibrahim's own calls (the name, the look, fade
never destroy, the headline, scripted lives only) are in the plan: https://claude.ai/artifact/9ZeFGovgtQHjGfKw7CJ8AN

## Step 0: the ruler (2 November 2026)

**E-01 Home.** `~/Developer/engram`, outside iCloud: iCloud evicted files from the old project's virtual environment
and stalled imports. The old CAMR (`~/Desktop/camr-repo`) is the baseline and is not changed by engram.

**E-02 One reader and one embedder for every contender.** Qwen3-1.7B-4bit reads; Qwen3-4B-Instruct-2507-4bit reads for
the "camr-4b" contender only. Qwen3-Embedding-0.6B-4bit-DWQ embeds. All run with MLX. Only the memory differs between
contenders, so the comparison is between memories, not models. The old CAMR's Ollama models are gone, so its engine
runs unchanged as a library (installed with `--no-deps -e`) with these models plugged in.

**E-03 The old CAMR as it shipped.** Its engine is configured exactly as CAMR Personal configured it
(`camr/app/assistant.py`):
- similarity ranking with a gate and entity bridging;
- notes found by keywords added to the vector hits;
- dates, time periods, profile notes, counting and the slot gate on;
- whole notes, and the app's 512-token context.

The record stores the camr commit and whether its engine files had local changes.

**E-04 Its similarity threshold, re-chosen for the new embedder.** The app's 0.50 belonged to its old embedder. The
threshold was chosen on the development lives (seed 0) by retrieval alone: does the packed context name the right
answer, and does the engine decline when nothing was told? 0.55 to 0.75 tie at 229 of 300 and 0.80 falls to 196.
The middle of that plateau, **0.65**, is used. See `records/calibration/camr-min-similarity.json`. Seed-1 lives were
never used.

**E-05 Lives.** There are three personas: a student, a dairy-cooperative manager and a developer. Seed 1 is for the
proof; seed 0 is for development and calibration. A life is fully fixed by its persona and seed. Each has 84 days,
about 330 messy notes and 100 questions:
- 45 single facts;
- 15 that change;
- 10 told across two notes;
- 15 dates;
- 15 never told.

**E-06 Time words are never misspelt.** A typo inside "yesterday" made the right date ambiguous even to a person, so
"today", "yesterday" and "morning" are exempt from the typo step.

**E-07 Grading is rule-based, not an LLM judge.** The same answer always gets the same verdict, a run costs nothing
extra, and anyone can re-grade. Verdicts are `right`, `stale` (names a value an update replaced), `missed` (declines a
told fact), `wrong`, `right_abstain` and `false_memory` (answers something never told).

**E-08 The growth metric** is facts answered right out of the 100, drawn against "told so far". Honesty is reported
separately, as false memories, so a contender cannot score by declining.

**E-09 The quiz** runs at the end of each week after that night's sleep: the same 100 questions every week, graded
against that day's right answers.

**E-10 Deterministic answers.** Decoding is greedy, Qwen3's thinking is off, and answers are capped at 40 new tokens.

**E-11 The wait** runs from question asked to first word. It includes retrieval for the old CAMR. For the perfect
reader it includes reading every note once, because a single question would have to. Within a quiz the perfect reader
keeps those notes as a cache and rewinds after each question, so a run takes minutes rather than hours.

**E-12 Provenance before the first commit.** Every record carries `engram_source_sha`, a hash of `engram/**/*.py`, so
it names the code that produced it.

**E-13 The baseline runs.** All twelve records (three lives × four contenders) came from code `a6beaea852f10d1a`.
That is the code in the first commit. The ending of a Claude session killed the first attempt in week 4 of the
student life's old-CAMR run. That partial record was set aside, not kept. `scripts/baselines.sh` was made resumable
and restarted, detached and with the Mac kept awake. The student life's first three runs were on battery and the
rest on the charger. On battery the old CAMR waited 1.31 s; on the charger, in the other two lives, it waited 1.31 s
and 1.28 s. The bare model waited 0.20 s, against 0.18 s and 0.19 s.

## Step 1: rooms and notes (2–3 November 2026)

All measured on the development lives (seed 0). The scripts are kept in `work/experiments/`.

**E-14 Honest SSD reads.** Rooms are written and read with the cache bypassed (`F_NOCACHE`), eight 1 MB pieces at
once. A room written that way and read straight back comes in at 3.4–5 GB/s, so it is coming from the SSD. The same
file written and read normally comes back at 24 GB/s from RAM, which would flatter every recall.

**E-15 A room is written as one continuous page.** Notes written one moment at a time and then laid side by side do
not work for a 1.7B model. Their positions are moved correctly: a single moment's notes give the same next word as
reading its words. But the question's attention spreads evenly over every separately written piece. Reading single
facts with the right moment among unrelated ones:

| Unrelated moments beside it | 0 | 4 | 12 | 30 | 60 |
|---|---|---|---|---|---|
| read as words | 35/46 | 33/46 | 31/46 | 32/46 | 26/46 |
| notes, each moment written alone | 35/46 | 21/46 | 10/46 | 2/46 | 0/46 |

Fixes tried without training, none enough:
- a 256- or 1,024-token neutral lead-in before each moment;
- sharpening the question's attention, as APE does;
- moving the repeated date prefix, or dropping it.

So each moment is written with its room's earlier moments in view. Inside one room, notes are then the same
computation as reading its words.

**E-16 One room on the desk, plus the closest moments as words.** Rooms written apart still lose the thread when
laid side by side. With 3 rooms, notes knew 96 of 255 facts against 144 from their words. Re-reading the first
tokens of each later room (as EPIC does) recovers in proportion to what is re-read: 64 tokens gave 124, at nearly
three times the wait. The design that won, over all 100 questions on three lives at day 83:

| Desk | Knows (of 255) | First word |
|---|---|---|
| words, 3 rooms | 144 | 1.65 s |
| notes, 3 rooms, + 4 closest moments as words | 142 | 0.35 s |
| 4 closest moments as words, no room | 135 | 0.45 s |
| notes, 1 room | 120 | 0.17 s |
| **notes, 1 room, + 4 closest moments as words** | **158** | **0.36 s** |

The room is the one holding the moment closest to the question. Its notes add 23 facts over the closest moments
alone. The closest moments are re-read as words in date order, just before the question, where they can see the
room.

**E-17 A new machine.** From 3 November everything runs on a MacBook Pro (Mac17,9, M5 Pro, 24 GB, with fans), not
the MacBook Air M4. Measured here:

| | MacBook Air M4 | MacBook Pro M5 Pro |
|---|---|---|
| reading text (prefill) | ~800 tokens/s | ~6,600 tokens/s |
| writing (decode) | 73–90 tokens/s | ~240 tokens/s |
| SSD, cache bypassed | 3.4–5 GB/s | ~12 GB/s |
| the same files from RAM | 24 GB/s | 60 GB/s |

The step 0 baselines (commits 776fecf, 1112b72) were measured on the Air. They stay as history, and all four are
re-run here. Runs and charts now use only records made on the current machine, and every record notes how busy the
machine was (`load_1m`). Answers also differ slightly between chips: the same engram setup knew 158 facts on the Air
and 164 here. E-14 to E-16 were measured on the Air; the tuning below was measured here.

**E-18 Room size and how many moments to re-read.** Tuned over 100 questions on the three development lives at
day 83 (knows, of 255):

| Rooms | 4 closest moments | 8 closest moments |
|---|---|---|
| up to 512 tokens, join 0.80 (rooms of ~210 tokens) | **164** | 164 |
| up to 512 tokens, join 0.75 (~390) | 153 | 163 |
| up to 1,024 tokens, join 0.75 (~590) | 143 | 158 |
| up to 1,024 tokens, join 0.70 (~950) | 139 | 152 |
| up to 2,048 tokens, join 0.70 (~1,480) | 131 | 146 |

Bigger rooms only add more to get lost in. The choice is rooms up to 512 tokens, join 0.80, and 4 closest moments,
which ties with 8 and makes fewer false memories. A single room on the desk is laid down without turning its keys,
since it sits exactly where it was written. That took the desk from 55 ms to 15 ms at 2,000 words.

**E-19 Step 1's pass marks, written before any proof-life (seed 1) run.**
1. *First word under 0.5 s with 2,000 words of memory* (the plan's "done when"). Measured by
   `python -m engram.ruler speed`: one room of that many words on the desk, read from the SSD with the cache
   bypassed, median of 5 tries.
2. *Accuracy matches reading the text* (the plan's "done when"). Summed over the three proof lives at week 12,
   engram knows at least 95% as many facts as `engram-words`, the same desk read entirely as words, and makes no
   more than 3 extra false memories (of 45).
3. *At least 10× sooner than reading the same words* (the plan's "proves"), at 2,000 words. That figure came from
   the Air, where reading ran at 800 tokens/s. Here reading runs at about 6,600 tokens/s and a trial gave 2.9× at
   1,000 words, so this mark is expected to fail on this machine. It is kept as written and the measured ratio will
   be reported either way.

Engram's place against the baselines is reported too, but the bar for that is the proof in step 6, not step 1.

**E-20 Step 1's results against its pass marks.** These are the three proof lives (seed 1) on the MacBook Pro M5 Pro,
3 November. Every record has 12 weeks, comes from code `e0c66092baca7fca`, and started at a 1-minute load of 1.4
to 5.7 (median 1.8).

| Mark | Result | |
|---|---|---|
| 1. First word under 0.5 s with 2,000 words | 0.233 s (588 MB read from the SSD in 0.046 s) | **pass** |
| 2. Knows at least 95% of `engram-words`, at most 3 extra false memories | 164 vs 163 facts; 25 vs 24 false memories; identical answers on 3,483 of 3,600 | **pass** |
| 3. At least 10× sooner than reading the words, at 2,000 words | 4.6× (5.8× at 3,000 words) | **fail** |

Mark 3 fails because this Mac reads text fast. Notes skip the reading but still pay for the SSD read and the copy into
GPU memory, about 0.1 s at 2,000 words. The head start grows with memory: 1.9× at 250 words, 3.7× at 1,000, 5.8× at
3,000. On the quiz itself the desk is one room of about 210 tokens, so notes save only 0.02 s there (0.070 s
against 0.090 s). Their weight shows in RAM instead: 1.82 GB against 2.20 GB.

Engram's wait stayed flat for all twelve weeks (0.066 to 0.070 s) and its peak RAM stayed between 1.74 and 1.83 GB,
while its notes on the SSD grew from 82 MB to 963 MB. Against the baselines on the same machine, week 12:

| Contender | Knows (of 255) | False memories (of 45) | Wait | Peak RAM |
|---|---|---|---|---|
| 1.7B alone | 0 | 0 | 0.05 s | 1.31 GB |
| perfect reader | 90 | 17 | 1.90 s, climbing | 2.77 GB |
| old CAMR, 1.7B | 166 | 29 | 0.15 s | 2.24 GB |
| old CAMR, 4B | 208 | 10 | 0.35 s | 3.58 GB |
| **engram, 1.7B** | **164** | **25** | **0.07 s** | **1.82 GB** |

Engram matches the old CAMR on the same model, at half the wait and 0.4 GB less RAM, without any of its
hand-written rules: no entity bridging, time filters or slot gates. It does not yet reach the 4B. Knowing more and
inventing less is the job of the later steps (the translation layer, sleep, and settling unsure facts at recall),
measured by the proof in step 6.
