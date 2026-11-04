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

CAMR v2's wait stayed flat in every week of every life (0.064 to 0.072 s) and its peak RAM stayed between 1.65 and 1.83 GB,
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

## Step 2: event log and first view (3 November 2026)

**E-21 What "used" means, and what watching costs.** While engram writes each word, it records that word's attention
over every node on the desk: the room's moments, and the closest moments re-read as words. Attention is averaged
over every head of four middle-to-late layers (12, 16, 20, 24 of 28). A node is *used* when it draws at least 10%
of the desk's attention over the whole answer; the others were only picked up. Measured on the development lives:

| Watching | Writing speed |
|---|---|
| off | 232.8 words/s |
| 4 layers | 231.5 words/s (−0.6%) |
| all 28 layers | 215.4 words/s (−7.5%) |

Four layers keep inside step 2's 5% limit. All 28 do not.

In 47 right answers to single facts, the node looked at hardest was the moment holding the answer every time; chance
was 12%. Any band of layers agreed (98–100%), so the four cheap ones lose nothing.

The log is one JSON line per event, `events.jsonl`, beside the rooms. A whole farmer life with 200 answers came to
0.26 MB, and writing it with the log on was 0.8% slower than with it off.

Per answer, a median of 7 nodes were picked up and 3 used. How much the top node draws already separates knowing
from not knowing:

| Answer | Top node's share (median) |
|---|---|
| right | 0.46 |
| wrong | 0.52 |
| false memory | 0.34 |
| missed | 0.19 |
| "I don't know" | 0.20 |

## Use cases: chat, errands and the brain view in one app (3 November 2026)

**E-22 Two days left, so the build order stops at step 2.** Ibrahim's call. The time goes to showing engram in use
instead:
- chat-style work;
- agentic work;
- the brain view, for assessing what went wrong or simply watching it work.

The translation layer, sleep and the full proof run (steps 3 to 6) become future work.

**E-23 The agent use case is errands made from the quiz.** Each quiz question becomes an everyday task whose tool
needs that exact fact: "Where does my vet live?" becomes "Book me a ride to my vet's home", which calls
`book_ride(destination)`. Ten pretend tools, including `ask_user`. A task is graded exactly like the quiz, on the
argument that should hold the fact: asking counts as declining, a wrong tool as a wrong answer.

The task instructions come after the notes. The chat template puts the tool list there too, so chat and errands
share one header and one set of saved notes.

On the development lives, a stricter wording ("every argument must be a value written in the notes") did no better:
41/85 and 41/85 on the farmer, 41/85 and 40/85 on the student. So the plain wording stays. Either way the 1.7B
model never called `ask_user`. It filled a never-told argument with a guess, or with words copied from the task
("mum's home").

**E-24 The app.** `python -m engram.app` serves one local page with four tabs: Simulation (added later, in commit 0c27183), Chat, Errands and Brain.
- **Chat:** a message ending in "?" is answered from memory; anything else is remembered as a dated moment.
- **Errands:** one task, one tool call, filled from memory.
- **Brain:** any answer or errand replayed word by word on the specimen view from the design rounds, with the
  traces strip underneath. For an errand, the strip shows only the argument values: the part that came from memory.
  A loaded life can be quizzed, so the Brain tab can sort what went wrong from what went right.

The server listens on 127.0.0.1 only. Memory lives in `~/.engram/default` and reopens where it left off. The map
layout is a plain-numpy t-SNE, which takes 1.3 s for 332 moments and is recomputed only when moments are added.

**E-25 The errands, measured.** The three proof lives (seed 1), the last day, all 100 errands each, on the MacBook
Pro M5 Pro. The 1.7B reader is the same for all three; only the memory differs. Added together:

| Memory behind the agent | Right (of 255 told) | Old value | Made up (of 45 never told) | Asked | First word |
|---|---|---|---|---|---|
| none (the 1.7B alone) | 1 | 0 | 44 | 0 | 0.15 s |
| the old CAMR | 40 | 6 | 45 | 0 | 0.16 s |
| engram | **122** | 16 | 42 | 0 | 0.19 s |

Engram does three times as many errands right as the old CAMR. Yet on the quiz the two are level (164 and 166 of
255, E-20). The old CAMR's gates and entity bridging were tuned for questions, and an errand worded as a request
("Book me a ride to my vet's home") falls past them. Engram opens the room holding the closest moment, however the
request is worded.

None of them ever asked. A 1.7B agent fills a never-told argument with a guess. That is the weakness to fix next
(settling unsure facts at recall, from the plan) and the clearest thing the Brain tab can show.

**E-26 A model sixteen times bigger, on the same Mac.** Qwen3.8-27B (4-bit, 16 GB, `mlx-community/Qwen3.8-27B-4bit`)
runs on the same MacBook Pro as every other contender. It keeps a running state instead of keys and values in 48
of its 64 layers, so it cannot use CAMR v2's saved notes. It reads CAMR v2's memory as words instead (`CamrWords`):
the same rooms, built by the same embedder with the same size cap counted in the 1.7B's tokens, and the same
choice per question. It is measured three ways on the held-out lives:
- alone;
- with CAMR v1, configured as for the 1.7B;
- with CAMR v2's memory as words.

Being about ten times slower per answer, it is quizzed at week 12 only, the week every table compares, and then
given the errands. The app is stopped during these runs so the 27B has the RAM.

**E-27 A crash window in the room files, found while documenting.** A moment's notes are appended to its room's
file at once, but the index that says where each moment starts is saved later. A crash in between left a room
file longer than its index. Every later moment in that room would have pointed at the wrong notes.

Opening a memory now cuts each room file back to the length its index records. The few notes written after the
last save are dropped, and nothing already saved is lost. There is a test. The fix was committed after the 27B
runs finished, so those records name the code that made them; the fix changes nothing in a run, since every run
starts from an empty memory.

**E-28 The 27B's tool calls were not being read.** The first two 27B errand runs scored 0 of 85 told and 15 of 15
"held back", because no reply was recognised as a tool call. Qwen3.8's chat template asks for
`<tool_call><function=name><parameter=key>value</parameter></function></tool_call>`. The parser only understood
Qwen3's JSON form. It now reads both, with a test for each, and every errand record keeps the raw reply so a format
surprise shows at once. The two runs are kept in `records/superseded/`, and all 27B errands were rerun with the
fixed parser. The 27B's quiz runs were unaffected: they need no tool calls.

## The rethink: the engine itself, its app and its proof (4 November 2026, overnight)

**E-29 The engine is the project.** Ibrahim's call, 4 Nov. The thesis title stands: "A Lightweight External Memory
Engine to Bridge the Capability Gap Between On-Device and Cloud Language Models". Everything else exists to show the
engine or to prove it.
- **Not a vector database.** Memory is tensors the model reads as if they were its own: saved keys and values.
- **Three layers**, swapped by what the task needs:
  - **subconscious:** an always-on core in RAM (`core.py`);
  - **conscious:** rooms of saved notes on the SSD, burst-read onto the desk; the hot ones stay in RAM (`swap.py`);
  - **archive:** a vault of linked plain-text notes, browsable like an Obsidian vault (`vault.py`).
- **Reach** sets who shares a memory: session, project, agent or global (`reach.py`).
- **Local only.** The engine serves models on this Mac (MLX). The one exception is a test of pairing with Ollama,
  where memory goes in as words.
- **Claude is only a yardstick.** It answers the same questions alone, with no memory. Every call logs its tokens and
  cost against a $60 cap for the night (`bench/cost.py`).

**E-30 Our own hard test: the Long Haul.** One scripted project: a developer building "Mama Njeri's Kitchen" over
110 working days, deterministic from a seed. It has 17,786 events and 2.01M tokens, cut at 64K, 256K, 1M and 2M.
Probes are planted early and asked late, and each has one answer a rule can check:
- facts;
- changed facts;
- two-hop links;
- corrected maths;
- a page that grows;
- code that must fit;
- look-alikes;
- things never said.

Each cut asks a stratified sample (10 per family, seed 0), so every contender gets the same 216 questions.

**E-31 Asking never teaches.** In the benchmark the engine's questions are read-only (`learn=False`). The hot
rooms, the LRU clock and the vault strengths are restored after every answer, so a question asked at 64K and again
at 2M is not helped by the first asking. Answers to questions asked at an earlier cut are flagged `asked_before`.
`--learn` turns learning back on, as in the app.

**E-32 Everyone reads the same instructions.** The engine, the words reader and Ollama paired read the yardstick's
wording, with "the history's notes" in place of "the history" (`LONGHAUL_INTRO`). Bare models read Claude's exact
wording, with lines joined as Claude's are; a test pins them byte for byte. Only what each one can see differs:
- Claude sees the newest part of the history that fits its 1M window;
- a bare local model sees the newest part that fits its own window (32K for the 1.7B and 8B, 64K for the 4B);
- the engine sees its notes.

**E-33 Ollama pairs through a proxy.** Ollama cannot save or restore keys and values, so the engine gives it memory
as words: a proxy on 11435 looks up the closest moments for each question and puts them in the system message
(`pair/`). Thinking is kept off. `qwen3:4b` is now the Thinking build, so the 4B runs as
`qwen3:4b-instruct-2507-q4_K_M`.

**E-34 The app's design is "Instrument".** It is the microscope picked on 2 Nov, with grafts from the other two
proposals:
- from Phosphor: rooms drawn as tensors, the RAM ruler and the bus line;
- from Living: the tensor beam and the reach aperture.

It scored 23 of 25 against 19 and 18 (`design/DECISION.md`). Six screens: Models, Chat, Code, Swarm, Memory, Bench.
There is no stock photography: the big pictures are live renders of real memory.

**E-35 One measuring job at a time.** Every benchmark runner raises a measuring flag (`~/.engram/measuring.json`).
While it is up, the app pauses its views and loads, downloads or probes nothing. The GPU queue runs one model at a
time; Claude runs beside it, since it needs no GPU.

**E-36 The Hugging Face suites run on Claude and Ollama, not yet on the engine.** `suite_run` refuses local MLX
contenders: the engine's instructions are the Long Haul's, and a suite needs its own frame. The suites are BABILong,
MATH-500, AIME and HARP correction pairs. Claude and Ollama (paired against bare) run them tonight.

Opus 5.5 sits the suites out. On the Long Haul it scored no better than Sonnet 5.5 (130 against 138 of 216), at
twice the price.

**E-37 The 1.7B's wording, not its memory, sank recall at 1M and 2M.** With the yardstick's wording the 1.7B engine
scored on facts 2/10 at 64K, 5/10 at 256K, 1/10 at 1M and 0/10 at 2M. Most of its total came from declining the
questions on things never said. Three checks on its own 2M memory (`records/bench/2026-11-04/diagnosis/`):
- **Retrieval was not the cause.** The room holding the planted fact was chosen for 6 of the 10 facts.
- **Sleep was not the cause.** 37 of the 40 recall answers hit an asleep room. Waking each room first (its notes
  written again from its words, `--wake`) gave 2/40 both ways.
- **The wording was the cause.** The desk held the fact, sometimes twice: for example "Muthoni Wafula is working off
  a Lenovo Yoga 7". The 1.7B still answered "I don't know", even with the same words as plain text in a fresh
  prompt. The yardstick's "Answer from them only. When they never say, answer I don't know" makes it decline what it
  can see.

On the same 2M desks, as words, the engine's own wording (`memory.INTRO`, from the 2–3 Nov quiz) got facts 6/10
against 1/10, but things never said 3/10 against 8/10. It recalls more and invents more. The 1.7B's honesty is a
property of its wording, not of its memory.

So the 1.7B is run both ways: the yardstick's wording, and its own (`--wording own`, names ending `+own`). Bare gets
the same wording, with its window as the notes. The 4B, 8B and 27B keep the yardstick's wording, as planned before
any result: no wording is picked after seeing it work on these questions. A softer wording written during the
diagnosis is recorded but not used.

**E-38 Speed does not grow with memory.** `local speed` on the 1.7B took points at 1K, 10K and 17.7K moments (112K,
1.15M and 2.01M tokens of history):
- first word p50: 0.11, 0.15 and 0.08 s;
- retrieval p50: 24, 17 and 18 ms;
- peak RAM: 4.26, 4.28 and 4.23 GB;
- disk: held at the 40 GB budget, with 920 rooms awake and 4,471 asleep at the end;
- ingest: about 1,100 tokens a second throughout.

The p90 first word (2–5 s) is a question whose room is asleep or whose answer is long, read as words.
