# Decisions

Technical calls made while building camr, each with its reason. Ibrahim's own calls (the name, the look, fade
never destroy, the headline, scripted lives only) are in the plan: https://claude.ai/artifact/9ZeFGovgtQHjGfKw7CJ8AN

## Step 0: the ruler (2 November 2026)

**E-01 Home.** `~/Developer/engram`, outside iCloud: iCloud evicted files from the old project's virtual environment
and stalled imports. The old CAMR (`~/Desktop/camr-repo`) is the baseline and is not changed by camr.

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

**E-12 Provenance before the first commit.** Every record carries `camr_source_sha`, a hash of `camr_engine/**/*.py`, so
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
machine was (`load_1m`). Answers also differ slightly between chips: the same camr setup knew 158 facts on the Air
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
   `python -m camr_engine.ruler speed`: one room of that many words on the desk, read from the SSD with the cache
   bypassed, median of 5 tries.
2. *Accuracy matches reading the text* (the plan's "done when"). Summed over the three proof lives at week 12,
   camr knows at least 95% as many facts as `camr-words`, the same desk read entirely as words, and makes no
   more than 3 extra false memories (of 45).
3. *At least 10× sooner than reading the same words* (the plan's "proves"), at 2,000 words. That figure came from
   the Air, where reading ran at 800 tokens/s. Here reading runs at about 6,600 tokens/s and a trial gave 2.9× at
   1,000 words, so this mark is expected to fail on this machine. It is kept as written and the measured ratio will
   be reported either way.

CAMR's place against the baselines is reported too, but the bar for that is the proof in step 6, not step 1.

**E-20 Step 1's results against its pass marks.** These are the three proof lives (seed 1) on the MacBook Pro M5 Pro,
3 November. Every record has 12 weeks, comes from code `e0c66092baca7fca`, and started at a 1-minute load of 1.4
to 5.7 (median 1.8).

| Mark | Result | |
|---|---|---|
| 1. First word under 0.5 s with 2,000 words | 0.233 s (588 MB read from the SSD in 0.046 s) | **pass** |
| 2. Knows at least 95% of `camr-words`, at most 3 extra false memories | 164 vs 163 facts; 25 vs 24 false memories; identical answers on 3,483 of 3,600 | **pass** |
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
| **camr, 1.7B** | **164** | **25** | **0.07 s** | **1.82 GB** |

CAMR matches the old CAMR on the same model, at half the wait and 0.4 GB less RAM, without any of its
hand-written rules: no entity bridging, time filters or slot gates. It does not yet reach the 4B. Knowing more and
inventing less is the job of the later steps (the translation layer, sleep, and settling unsure facts at recall),
measured by the proof in step 6.

## Step 2: event log and first view (3 November 2026)

**E-21 What "used" means, and what watching costs.** While camr writes each word, it records that word's attention
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

**E-22 Two days left, so the build order stops at step 2.** Ibrahim's call. The time goes to showing camr in use
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

**E-24 The app.** `python -m camr_engine.app` serves one local page with four tabs: Simulation (added later, in commit 0c27183), Chat, Errands and Brain.
- **Chat:** a message ending in "?" is answered from memory; anything else is remembered as a dated moment.
- **Errands:** one task, one tool call, filled from memory.
- **Brain:** any answer or errand replayed word by word on the specimen view from the design rounds, with the
  traces strip underneath. For an errand, the strip shows only the argument values: the part that came from memory.
  A loaded life can be quizzed, so the Brain tab can sort what went wrong from what went right.

The server listens on 127.0.0.1 only. Memory lives in `~/.camr/default` and reopens where it left off. The map
layout is a plain-numpy t-SNE, which takes 1.3 s for 332 moments and is recomputed only when moments are added.

**E-25 The errands, measured.** The three proof lives (seed 1), the last day, all 100 errands each, on the MacBook
Pro M5 Pro. The 1.7B reader is the same for all three; only the memory differs. Added together:

| Memory behind the agent | Right (of 255 told) | Old value | Made up (of 45 never told) | Asked | First word |
|---|---|---|---|---|---|
| none (the 1.7B alone) | 1 | 0 | 44 | 0 | 0.15 s |
| the old CAMR | 40 | 6 | 45 | 0 | 0.16 s |
| camr | **122** | 16 | 42 | 0 | 0.19 s |

CAMR does three times as many errands right as the old CAMR. Yet on the quiz the two are level (164 and 166 of
255, E-20). The old CAMR's gates and entity bridging were tuned for questions, and an errand worded as a request
("Book me a ride to my vet's home") falls past them. CAMR opens the room holding the closest moment, however the
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

**E-35 One measuring job at a time.** Every benchmark runner raises a measuring flag (`~/.camr/measuring.json`).
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

**E-39 Past 2M: the same questions under one and two million more tokens.** Ibrahim asked to push past 2M, to 3M and
4M. `camr_engine.bench.haul.extend` keeps the 110 days and every probe exactly as they are (checked event for event).
It then adds 110 more working days of noise only, from the same generators with random streams of their own,
and the longer script passes the same fairness checks. The 3M and 4M cuts ask the 2M cut's 73 questions: a cut
where nothing new has become askable reuses the cut before's sample. So any change in score is the history's
weight, not new questions. The 4B (engine and bare) runs at 3M and 4M first. Claude Haiku and Sonnet run there
too; their 1M window holds only the last days, which have nothing planted.

**E-40 The engine's process held 19 GB; MLX's buffer cache is now capped at 1 GB.** Ibrahim asked to optimize RAM.
During the 4B's 4M-token run, the process's physical footprint (what Activity Monitor shows) was 19.2 GB:
- only 1.0 GB was resident;
- the rest sat compressed or in swap, which was full (8.8 of 9.2 GB).

The records' "peak RAM" of 5.7 GB is MLX's peak of arrays in use during one answer, so it never saw this.

The cause is MLX's cache of freed GPU buffers. It is unbounded up to the GPU limit (about 18 GB here), and a long
ingest frees a desk's worth of buffers for every moment.

`camr_engine.models.limit_cache` now caps it when a reader or embedder loads: 1 GB by default, `CAMR_MLX_CACHE_GB` to
change it, `off` for MLX's default. It changes no computation, only how many freed buffers are kept for reuse.

Every checkpoint and speed point now records the process's footprint (`footprint_gb`, from libproc) beside MLX's
peak. `camr_engine.bench.ram` measures the cap against no cap in fresh processes, with footprint over time, ingest speed
and first word. It runs after the queue. The 8B, 27B and Ollama runs are the first measured with the cap. Every run
before them (1.7B and 4B) ran without it; their scores are unaffected, and their RAM is now known to be understated.

**E-41 The cap, measured: a third of the RAM, almost twice the speed, the same answers.** The 4B was rerun on the
4M script with the 1 GB cap (E-40). At 3M, against the same run without the cap that morning:
- **answers:** 29 of 73, with identical verdicts (deterministic, as it should be);
- **footprint:** 19.2 GB down to 7.5 GB;
- **reading the 3M history:** 99.5 min down to 53 min (503 to 938 tokens a second), since nothing swapped;
- **first word p50:** 0.37 s down to 0.31 s;
- **retrieval p50:** 20 ms down to 16 ms.

7.5 GB is about what the parts add up to: the 4B's weights, the embedder, the 2 GB pool of hot rooms, the 1 GB
cache and Python. Records: `100255-longhaul-engine-qwen3-4b.json` (before), `143706-longhaul-engine-qwen3-4b.json`
(after).

**E-42 Project reach is the best reach; global is close; a session alone is not enough.** The 4B engine heard the
Long Haul's first 256K tokens four ways and was asked the same 40 questions (`camr_engine.bench.reach_run`):

| Set-up | Right of 40 | Facts | First word p50 | Disk |
|---|---|---|---|---|
| session (each week its own memory; asked in the last week's) | 11 | 0 of 10 | 0.24 s | 44 GB |
| project (every week into one project memory) | **26** | 8 of 10 | 0.19 s | 44 GB |
| global (this project and another seed's, in one memory) | 24 | 8 of 10 | 0.19 s | 85 GB |
| project + global (read both, best room wins) | 24 | 7 of 10 | 0.19 s | 85 GB |

- **session:** the last week holds only that week, so 10 of its 11 are never-said questions declined.
- **global:** two maths answers went stale, because they took the other project's look-alike rule.
- **project + global:** the other project's room won 7 of the 40 questions and cost exactly 2 answers (a fact and
  a changed fact). The 4B declined both rather than answer with the other project's facts.
- **never said:** 10 of 10 declined in every set-up.

So the app's default stays project reach. A session reads its project before global, and global's room should win
only by a clear margin; that is not built yet. Records: `195128`, `195633`, `200137` and `201043-reach-engine-qwen3-4b-*.json`.

**E-43 The Ollama suite runs redone where the runner, not the model, set the score.**
- **BABILong, bare:** 58 of the bare 1.7B's 100 answers were thrown out as "thinking" with zero characters of
  thinking. With a long prompt qwen3 opens its answer with the `</think>` that its think-off template ends the
  prompt with. An empty block is now cut off the answer, real thinking is still an error, and the run was resumed
  for the 58.
- **HARP:** at the shared 400-token limit, 82 of the bare 1.7B's 120 answers and 95 of the paired one's were cut off
  mid-working. Claude had 400 + 8,192 tokens to think in; the 1.7B's thinking is off, so it can only work in its
  words. `--work-room 8192` gives it the same room. Both 400-token records are kept, and the rerun is a new record
  beside them.
- **BABILong, paired (unaffected):** 20 of 100. The pairing's 512 tokens of notes miss most "where is X now"
  answers, which need the latest of many mentions.

**E-50 Swarm removed: the app is Chat and Code.** The Swarm screen, its routes (`/api/swarm/*`), `agentic/swarm.py`, the
Bench "Swarms" tab and the stage's `well` mode are gone; the shared RAM pool, `engine_brains` and the agent reach stay,
since Code uses them.

**E-47 An OpenAI-compatible endpoint with memory, built from the Ollama pairing's code.** `camr serve`
(`camr_engine/pair/openai.py`) listens on 127.0.0.1:11436, next to the pairing's 11435. Its routes are
`/v1/chat/completions` (streamed or whole, with memory), `/v1/models`, and the other `/v1/` paths (passed through).
Nothing outside `/v1/` is served.
- **Backends:** Ollama (11434), LM Studio's server (1234), and mlx_lm.server (8080). All three already speak this API,
  so `Endpoint` is the pairing's `Pairing` narrowed: one path gets notes, and only `/v1/` is forwarded. The proxy,
  the tap, the security and the metrics are the same code. `Pairing` gained `memory`, `serves()` and `name` for this;
  the Ollama pairing behaves as before (its 40 tests pass unchanged).
- **The same memory folder** (`~/.camr/default`, notes under `ollama/`): a note comes back whichever door it came in
  by. The folder name stays, so existing pairing memories still load.
- **Agents:** an answer that ends by calling a tool (`finish_reason` "tool_calls") is no longer remembered, in either
  door. Before, a tool loop remembered the question again with every step that had words. The notes still go in
  front of the last user message on every step, so they stay with the question through the loop. The answer that ends
  the turn is remembered once, with it.
- **The native engine (tensors) is not behind these routes yet.** Through all three backends, memory goes in as words.
- **Tested:** 10 tests against a stand-in backend. The OpenAI Python SDK 3.45 and `@ai-sdk/openai-compatible` 3.0
  (what OpenCode's config names) were run against the stand-in. One smoke test went through the real Ollama with
  qwen3:1.7b: a fact told, then asked back streamed, came back right ("Pilipili") with 187 characters of notes.

**E-48 One `camr` command, and installers that keep the engine in an environment of its own.** `camr_engine/cli.py`
is the `[project.scripts]` entry: `serve`, `ollama`, `app`, `doctor` (it only looks: no model, nothing past
127.0.0.1), `bench` (pointers) and `version`.
- **The old CAMR baseline also installs a command named `camr`.** So no route installs the engine into an
  environment that might hold the old one. `packaging/install.sh` uses `~/.camr/engine`, not `~/.camr/venv`, which
  the CAMR Personal installer uses. The dev venv was not reinstalled.
- **install.sh** uses uv when it finds uv, else `python3 -m venv`. It resolves the interpreter's real path first: a
  venv made through a link to uv's standalone Python (`~/.local/bin/python3.12`) could not find its standard library.
  Tested into temp HOMEs both ways, from the local v2 folder.
- **npm** (`packaging/npm`, `camr-memory`) is a launcher. It installs the engine with the same `install.sh` on first
  run, then runs `camr`. It is not a second copy of the engine. Tested with `npm pack` and from a clone, into temp
  prefixes.
- **`uv tool install` was tested; pipx was not** (it is not installed). The Homebrew formula
  (`packaging/homebrew/camr.rb`, head-only, with a `brew services` entry) passes `ruby -c` but was never run: there is
  no Homebrew here and no tap.
- Nothing was published: no npm package, no tap, no release.

**E-49 The landing page is static, and carried by the app's own screenshots and the Long Haul's numbers.** `site/`
is HTML, CSS and a little JS (tabs, copy buttons, the chart), with no build step.
- **Colour means something:** memory is cyan, the model is amber, and Claude (the yardstick, with no memory) is grey
  and dashed. The chart's marks are validated for a dark surface. Claude's grey fails the chroma floor on purpose; the
  dash and the direct labels carry it.
- **The chart plots the share right**, since the cuts ask 34, 40, 69 and 73 questions; the counts are in its tooltip
  and its table. It shows the whole story: Sonnet leads up to 2M, then falls to 13 and 10 past its window, while the
  engine stays at 29.
- **Screenshots:** the native Mac app's (`apps/mac/screens/`, the 4B with 256K tokens of the Long Haul in memory),
  copied into `site/screens/mac/`. Each is one `<img>` line, so a new one is a one-line swap. The hero is the weights
  view: the chosen room (cyan) flowing into all 36 layers (amber), the same two colours as the page. The results
  carry the app's own memory-on/off demo ("KDS 711Z" in 231 ms, then "I don't know"). The web app's screenshots and
  `swarm.png` are not used.
- **No photography:** none in the repository has a known licence, and nothing was downloaded.

**E-44 Files into memory: a vision model turns them into words once, and the notes stay words.**
`camr_engine/media.py` is the app's way in: `ingest(path, memory, *, describe=None, day, date=None, stamp=None,
tags=())`.
- **What a file becomes:**
  - a PDF, one moment a page (pypdf's layout mode, so a table row stays on one line);
  - an image, its caption and what is written in it (two asks to the vision model);
  - a video, a frame every 2 s, each described with its time. A frame whose 64 × 36 thumbnail barely changed is
    read once: shake and grain change no pixel by 40 grey levels, a new line on a board changes 2–5% of them.
- **Where it came from:** every moment's words start with the file and its page or frame, its vault note is tagged
  `file` and its kind, and `vault/files/sources.jsonl` maps the moment to the file. The file is copied into
  `vault/files/` (named by its hash), with the frames a video was read from.
- **The vision model reads the notes as a 1.7B does.** mlx_lm loads Qwen2.5-VL-3B's language half without its
  vision tower. Its M-RoPE turns a word by the same position on all three axes, which is plain RoPE (mlx_lm runs it
  as `nn.RoPE`), so the notes need nothing new: `models.text_args` shows that half to the Notebook. The vision half
  is loaded separately through mlx-vlm (`models.Seer`), 1.7 GB more of the same weights.
- **Looking again is words plus the image, not notes.** An image's tokens sit at positions in three dimensions, and
  the notes are written for words. So `media.look` (when the closest moment came from an image) gives the vision
  model the room's and closest moments as words and the image itself. `Memory.answer` is unchanged.
- **Gemma 3 is not an engine reader.** Its local layers slide over 1,024 tokens, its global layers scale RoPE by 8,
  and its tokenizer puts a BOS before every encoded moment. The Notebook refuses the scaled RoPE as it should.
  Gemma reads files (mlx-vlm) and could describe them; it does not read notes.
- **Ollama:** `qwen2.5vl:3b` is pulled. `gemma3:4b`, and `qwen3-vl:4b-instruct` as a stand-in, need a newer Ollama
  than 0.13.5. Ollama was not upgraded under a running queue, so (e) is the one Ollama vision model.
- **Packages:** mlx-vlm 0.7.12, pypdf, reportlab, matplotlib and imageio-ffmpeg went into the venv. Of what was there,
  only fsspec moved (2026.9.0 to 2026.7.0). mlx, mlx-lm and transformers are as they were.

**E-45 Multimodal memory, measured: with the engine, the files are as good as in the prompt.**
`camr_engine.bench.media_run` tells 21 files (5 PDFs, 8 photos, 5 charts, 3 videos; 29 planted facts and 8
never-said questions) among 99K tokens of the Long Haul's events, all told by 60K, then asks.
- **Seed 1, right of 37:**
  - `engine:qwen3-4b` reading Qwen2.5-VL-3B's words: 37;
  - the same, reading gemma3:4b's words: 36;
  - `file:qwen2.5-vl-3b` (the file in the prompt): 34;
  - `ollama:qwen2.5vl:3b` paired: 34;
  - `engine:qwen2.5-vl-3b`: 33;
  - its rooms asleep: 33;
  - with `+look`: 32;
  - `ollama:gemma3:4b` paired: 28;
  - `bare:qwen3-4b` (64K): 17;
  - Ollama bare: 5 and 5;
  - `bare:qwen2.5-vl-3b` (32K): 0.
- **Seed 2:** 35, 33, 33, 31, 18, 2 and 2 in the same order (4B engine, file, Ollama paired, VL engine, bare 4B,
  bare VL, Ollama bare).
- **Facts:** the VL engine got all 29 planted facts (seed 2: 27), the same as with the file in the prompt (29, 29).
  Every miss of the VL model is a never-said look-alike (another supplier's total, the other branch's meeting time),
  with or without the engine. The 4B declined all 16 never-said questions over the two seeds.
- **Notes or words:** the VL engine with a 0.5 GB disk budget (every room asleep, read as words) scored the same 33
  with the same misses. So the 4B's lead comes from the model, not from the notes. It was run with a 4 GB budget,
  since its notes would take 16 GB and the disk had 13–17 GB free; 36 of its 37 answers read asleep rooms as words.
- **Look:** showing the image again changed no fact (all were right from the words), lost one never-said question
  and took the first word from 0.21 to 0.80 s. It stays in `media.look` for the app, and off by default.
- **Cost of a file:** describing the 21 files took 75 s (MLX) and 65 s (Ollama); 29 moments, 3.7K tokens.
  Ingest ran at about 1,250 tokens a second for the 3B and 1,000 for the 4B. The VL engine's memory was 4.4 GB on
  disk (36 KB a token), in a 5.1 GB process.

**E-46 What the night changed in the multimodal run, and what it did not measure.**
- **Qwen2.5-VL's vision tower runs in bfloat16.** In float16 it overflowed on two of the eight photos (the meeting
  and fumigation notices), and every word came out "!". It did so at every size tried (768 to 1,280 px) and was
  fixed by bfloat16, which changes nothing else. `media` now drops such words instead of keeping them. The first
  description (with "!!!!") was thrown away, and every record comes from the second.
- **A concurrent edit of `Reader` dropped the line that lets a vision checkpoint's language half read notes.** It is
  back (7798cc9). The two runs it broke left records that failed at opening; they were deleted, not committed.
- **Disk:** 516 GB of old memories sit in `work/memories` (not this run's, left for Ibrahim). Each media run's memory
  is deleted once its record is written (`run --keep` keeps it). Free space stayed above 8 GB.
- **Ollama:** it was updated to 0.40.14 during the night (not by this run), which made `gemma3:4b` pullable. It was
  pulled, run, then removed to keep the disk margin. The MLX gemma-3-4b download is incomplete and was not used.
- **Not measured:**
  - gemma 3 as an MLX reader or describer;
  - the 4B with every room awake (no disk for it);
  - a third seed;
  - real photographs (the photos are rendered: turned, blurred and grainy, but not taken with a camera);
  - audio;
  - videos longer than 12 s.
  The bare Ollama runs' first word is not reported, since Ollama read the whole window again for every question.

**E-51 Shelves: memory kept apart by kind of work, and read as one.** Ibrahim asked for compartments the app can
show: Projects, Coding, Research and Personal (`camr_engine.shelves`). Each shelf is a reach of its own. Projects is
the global reach, so the Long Haul seeded there needed no move, and the other three are project reaches.
- **Reading:** with shelves on, a chat reads every shelf and the closest note wins, as a session always chose.
- **Remembering:** a moment goes on the shelf picked. "Auto" puts it on the shelf whose description and three
  example moments it is closest to, using the embedder's own measure. On twelve test sentences it filed all 12
  right, 8 of 8 among those not close to the examples. In the app, three moments went to Coding, Research and
  Personal, and each answer read the right one.
- **Code:** it keeps what it learns on the Coding shelf and still reads its workspace's own reach.
- **Names:** the app calls a room a note, and a group of notes by topic a shelf. The engine's code keeps `rooms`.
- **The web app:** shelves stay off unless a client turns them on, so its reach picker reads exactly what is picked.

**E-52 Warm before the first question.** Once a session opens, a one-word answer builds the model's kernels, and the
newest notes of every shelf are read off the SSD (1.5 GB shared between shelves), so the operating system holds
them in RAM. On the 4B the kernels alone save 24 ms of the first answer's wait (111 to 87 ms). Notes read ahead are
fetched from RAM instead of the SSD. A note not read ahead still comes off the SSD in milliseconds: the first Long
Haul question read 68 MB in 8 ms, and its first word came at 230 ms. The app shows the warming, notes lighting on
their shelves.

**E-53 Three models for the demo: Qwen3 1.7B, 4B and 8B.** At Ibrahim's request the rest were moved to the Trash,
with their records kept: the 27B, Qwen2.5-0.5B, Qwen2.5-VL 3B (once the multimodal benchmark ended), a partial
Gemma 3 download, and 511 GB of finished benchmarks' memory folders. Emptying the Trash is his to do. The Ollama
vision model (`qwen2.5vl:3b`) is left for him to remove: `ollama rm qwen2.5vl:3b`.

**E-54 Notes kept at 8 bits on the SSD, and an 8 GB disk budget per reach in the app.** The app's seeded memories
took 32-41 GB each (112 KB a token on the 1.7B, 144 KB on the 4B and 8B). Rooms now keep their notes at 8 bits by
default (`Memory(bits=8)`, `camr_engine.notes.pack`): every 64 numbers along a head share a 16-bit scale and offset, so
a token is 17/32 of its 16-bit size and rooms still grow by appending. Each room's bits are in the index and in its
file's name (`room-000001.q8.notes`), so 16-bit rooms from before still read.
- **Measured** on the Long Haul, `engine:qwen3-1.7b`, 64K and 256K (74 questions), one run each:

  | Bits | Right (64K, 256K) | Rooms at 256K | First word p50 at 256K | SSD fetch p50 at 256K |
  | --- | --- | --- | --- | --- |
  | 16 | 14, 20 | 34.3 GB | 0.098 s | 4.9 ms, 54 MB |
  | 8 | 14, 19 | 18.2 GB | 0.094 s | 2.5 ms, 29 MB |
  | 4 | 14, 18 | 9.7 GB | 0.146 s | 2.0 ms, 15 MB |
  | 8, 8 GB budget | 14, 20 | 8.6 GB, 366 of 759 rooms asleep | 0.126 s | 0.1 ms, 1 MB |

- **Why 8 and not 4.** At 8 bits 61 of 74 answers were word for word the 16-bit ones and one verdict changed (a
  remembered backup time became "I don't know"): within noise. At 4 bits only 48 were the same and two answers were
  lost.
- **The budget.** The app's sessions give each reach 8 GB of awake notes (`CAMR_SHELF_DISK_GB` sets another). It is
  held in the warm-up (`shelves.hold`, on the session's thread before any question) and each time a moment is kept.
  The Long Haul at 256K, 8-bit, with 8 GB kept its 20 right with nearly half its rooms asleep, at 28 ms more to the
  first word, since an asleep room is read as words.
- **Existing memories** are packed in place by `python -m camr_engine.shrink <reach> [--apply]`: each 8-bit copy is
  checked against the old notes before the index names it and the old file is deleted.
- Records: `records/bench/2026-11-05/*longhaul-engine-qwen3-1.7b-{16bit,8bit,4bit,8bit-8GB}.json`.

**E-55 The chat is an assistant, and the model decides when to reach into memory.** Ibrahim found the chat answering
"show me step by step" with "I don't know": every question went through memory's strict answer ("only the notes,
else I don't know"), with no conversation.
- **Why not a closeness threshold:** in the Long Haul memory, "hello" sits at 0.81 from its nearest moment and "What
  is Otieno's surname?" at 0.72, so closeness cannot separate the two kinds of question.
- **The router:** the model routes each message with a one-word answer (MEMORY or GENERAL) that reads the last two
  turns, so follow-ups stay with the conversation. It adds about 0.1 s, and its word is never shown.
- **MEMORY:** the notes path as before, with conversation rules after the notes. The closest moment of every other
  shelf is read too, as words, when it is within 0.12 of the best. That near-tie read found a photographed receipt
  that 737 Long Haul notes had outscored (0.70 against 0.81).
- **The router sees memory:** a question naming a person or business found in its five closest notes goes to
  memory outright; otherwise the model judges with the closest note in view. Routing blind, the 8B sent "the
  number plate of Kitengela Ventures' delivery truck" to its own knowledge. Seeing memory, it routed 13 of 14 test
  questions right on its Long Haul memory. The miss was a never-said name, which the model then answers honestly.
- **GENERAL:** the model answers from its own knowledge with the last six turns, and thinks aloud when it is a
  thinking build and the user wants to see it. Qwen3 1.7B and 8B can think; 4B Instruct 2507 cannot.
- **Research:** reads the best Wikipedia page through its public API. The page goes into the user's turn as marked
  data, never into the system prompt.
- **Learning:** what was asked and answered is kept on a shelf, the source with it. Web moments are tagged web, and
  general knowledge goes on Research.

**E-56 Memory that revises itself, never by deleting.** Before a moment is kept, it is compared with the closest
moment of the same source (user, file or web, by the vault tags it was kept with).
- **Only close pairs are judged:** below 0.78 closeness a moment is simply kept. A close pair gets a one-word judge:
  SAME, UPDATE or NEW.
- **UPDATE:** keeps the new moment, saying which note it updates, and tags the old note superseded and links the
  two.
- **SAME:** leaves a repeat out only when it is also 0.95 close and the judge said exactly SAME. Nothing the user
  says is lost on the judge's word alone.
- **On the 4B:** a raised minimum order and new opening hours were judged updates, a repeat the same, and a
  birthday and another branch's hours new: 5 of 5.

**E-57 Eyes: a vision model that also reasons.** Images and videos dropped into the chat are read into memory by
Qwen3-VL-4B-Thinking (mlx-community, 4-bit, 3.1 GB), loaded the first time a picture needs it. It read a
photographed receipt line by line (total KES 730.00, paid by M-Pesa) in about 25 s with the load, and the 8B then
answered both questions about it from memory. PDFs are read as text at once; describing their pictures with a
thinking model would take minutes. A file's moments say they are not the user's words.

**E-58 Code: café websites, a benchmark for building from what was told.** `camr_engine.bench.code_run` tells memory
six notes about a café (name, two brand colours as hex, three menu items with KES prices, hours, address, and the
rule "prices always show KES and two decimals"), then asks the Code agent, in an empty workspace, for "a one-page
website for our café: index.html and style.css". Ten rules grade each site with no model, "nothing invented"
among them. Four ways: off (no memory, no notes), the notes in the prompt (the ceiling), memory (the notes on the
Coding shelf the day before), and note context (the notes ten days back among 6K tokens of Long Haul events).
- **Why these rules:** each one is a fact only the notes hold, or a plain sign the page works. The menu words that
  count as invented are a fixed list, so a site that adds a latte to a café without one fails.
- **Shell refused:** the sites need only file writes, so the benchmark's gate denies every command at once and
  counts the asks.
- **Results, rules passed per site (of 10), five cafés:** Qwen3 4B: off 3.0, in the prompt 9.8, memory 10.0, note
  context 9.2. Qwen3 8B: off 4.0, in the prompt 10.0, memory 9.6, note context 9.2. Records
  `records/bench/2026-11-05/*-code-cafe-*.json`.
- **What the note-context misses are:** each time the price rule was missed (three runs), its note was among the
  words memory put on the desk, and the model still wrote "KES 220". One café's colours and address were in neither
  the room memory picked nor its closest words. The 8B also missed one café's colours that were in its room.

**E-59 The Code agent finishes what it starts.** Before these changes, with memory on, the 4B answered "I don't
know." or listed the empty folder until its 12 steps ran out: 0 of 10 rules on each café tried. Each change is
small and has its test (`tests/test_agentic.py`):
- **The notes' rules no longer end a task.** The engine's header tells the model to answer in one sentence or say
  "I don't know"; the agent's instructions after the notes now say both do not apply to a task, and to follow every
  rule the notes give.
- **Paths:** "a.txt, not {workspace}/a.txt". The 4B wrote `site/index.html` inside the folder `site`.
- **An empty workspace is named** on the first step, and every step names the files the task asks for that are not
  written yet.
- **A look made again with no write since is not run again.** The model reads "the same as [2]: nothing has changed
  since"; after two of those in a row its next step is offered only the tools that change things.
- **A reply cut off inside a tool call** (a whole page is long) is told so, and the next reply gets twice the room,
  up to 4,096 tokens.
- **An answer that says "I will now create style.css"** while the task's files are not all written is sent back
  once. The 8B did this on one café, and said it again instead of writing the file, so that site has no stylesheet.
- **A code step re-reads its 8 closest moments as words** (a short answer reads 4): a page needs more facts.

**E-60 Looks are worked out at once.** The attention each written word pays to the desk was kept lazy, so every
look held its layer's keys until the answer ended: by our count about 100 MB a word on a 3K-token desk. On one
café's note-context run the GPU ran out (Metal "Insufficient Memory") at the first step, every time. Each look is now
evaluated as it is made, and prompt chunks are not looked at at all (nothing reads them). That run now passes 9 of
10.

## CAMR against conventional RAG on the Long Haul (5 November 2026)

**E-61 Pre-registered before any held-out (seed-1) run: the contenders, the cuts, the metrics, and what counts as
CAMR beating RAG.** Written after the development memory (seed 2) was told and before any of its questions were
answered; nothing on seed 1 has been run for this comparison.
- **Reader and memory, the same for every contender:** Qwen3 4B Instruct 2507 (4-bit, MLX), the Qwen3-Embedding-0.6B
  embedder, the Long Haul's dated moments (`[YYYY-MM-DD, day N] text`), the yardstick's instructions as the engine
  reads them (`LONGHAUL_INTRO`), "Today is ...", the family's line, the same questions and the same rule grader. The
  1 GB MLX buffer cap (E-40) is on for all of them.
- **Contenders, on the seed-1 Long Haul:**
  - `rag:qwen3-4b`, conventional RAG (`camr_engine.bench.local.Rag`): ingest embeds each moment and keeps its words;
    a question is embedded and the 8 closest moments are pasted in as text where the engine's notes go, closest first
    while they fit **1,024 tokens**, then laid in date order (as the engine re-reads its closest moments). Only the
    fixed header is already read. 1,024 tokens is the memory CAMR's desk holds: one room of at most 512 tokens plus
    4 closest moments of about 115 tokens each. Every answer records the memory actually in view, so the match can
    be checked rather than assumed.
  - `engine:qwen3-4b` **improved**: the desk chosen on the development memory by the rule below, with a disk budget
    of 200 GiB (`--disk-gb 200`) so the 4B's 8-bit rooms (about 78 KB a token) stay awake through 2M tokens instead
    of sleeping past about 0.5M at 40 GB. Its memory is cloned at every cut (`--snapshots`).
  - `engine:qwen3-4b` **old desk** (one room + 4 closest moments as words), read from those same clones
    (`camr_engine.bench.desk`), so it differs from the improved one only in the desk. The 4 November record
    (`071525-longhaul-engine-qwen3-4b.json`: 16-bit notes, 40 GB) stays the "as shipped" history.
  - `bare:qwen3-4b`, the most recent 64K tokens, the yardstick's own wording, as before.
- **Cuts:** 64K, 256K and 1M (34, 40 and 69 questions, sample seed 0), and 2M (73) if the time allows. One measuring
  job on the GPU at a time.
- **Choosing the improved desk (development only):** the candidates are the desks listed in E-62, read from the
  seed-2 memory at 256K and 1M (10 questions per family, sample seed 0). The one with the most right answers summed
  over both cuts is adopted, ties going to the lower first-word p50 at 1M, but only if it beats the old desk by at
  least 2 answers; otherwise the old desk stays and the improved contender is the old desk with the larger disk
  budget. Nothing is tuned on seed 1.
- **Metrics, per cut:** right answers (and by family; stale answers on changed facts; false memories on things never
  said); first word p50 and p90; total time p50; tokens read as text before the first word (prefill) p50; memory in
  view p50 (notes already read plus memory read as text); retrieval ms p50; the process's peak footprint
  (`ri_lifetime_max_phys_footprint`); disk; ingest tokens per second.
- **What counts as CAMR beating RAG**, metric by metric: more right answers (summed over the cuts run, with an exact
  two-sided McNemar test on the paired answers; "significantly" only below p = 0.05, otherwise "level"); fewer stale
  answers; fewer false memories; lower first-word p50 and p90; lower total-time p50; fewer prefill tokens; more
  memory in view; lower retrieval ms; lower peak footprint; less disk; faster ingest. Each is reported whichever way
  it goes. Expected before running: RAG wins disk, ingest and retrieval ms; CAMR wins first word and prefill; the
  answers are open.
- **The equal-memory curve**, at the seed-1 1M cut: RAG with 512, 1,024, 2,048 and 4,096 tokens of moments (k 64, so
  the budget binds) and CAMR with as many rooms as fit 512, 1,024, 2,048 and 4,096 tokens of notes, plus the improved
  desk's closest moments as words. Right answers and first word against the memory in view each measured. Expected:
  RAG's first word grows with the text it re-reads; CAMR's stays nearly flat.

**E-63 Finding by words, line by line (development only, seed 2).** Where the Long Haul's answers were lost, measured
before changing anything (`camr_engine.bench.haul.recall`): for each of the 63 told questions in the seed-2 1M sample,
how high the moment holding the answer ranks among the memory's 8,740 moments. A question counts only the moments it
needs (the newest value of a changed fact, the asked one of two lookalikes, both hops of a two-hop).

| Finder | in the closest 4 | 8 | 16 |
|---|---|---|---|
| the embeddings (the engine until now) | 18 | 21 | 27 |
| BM25 over whole moments | 40 | 44 | 47 |
| BM25 line by line, a moment scoring as its best line | 40 | 45 | 48 |
| lines + a second look for the bridge + the embeddings, fused (`finder=words`) | 41 | 49 | 49 |

A moment is often a whole meeting note or a pasted group chat; one embedding for all of it blurs the one line a
question needs, while a rare word (a name, a plate, a route, a price) finds it. The second look searches for the
words the best line adds and the question lacks (the bridge of "Kevin handles payroll" for "which extension will
Kevin get"), at three quarters of the first look's weight so it never undoes an exact name; the embeddings count
half. These three weights were swept over 27 settings on this sample: every setting gave 44 to 49 in the closest 8,
so the choice is not fine-tuned. A request to build a page also looks for the design system's words. Maths questions
stay lost (a method taught once, asked again with new numbers, ranks 11th to 46th): that needs its own step.

Answered by the 4B from the seed-2 1M memory (`camr_engine.bench.desk`, the yardstick's wording, 73 questions):

| Desk | Right | First word p50 | Memory in view p50 |
|---|---|---|---|
| one room + 4 closest moments by embeddings (until now) | 34 | 0.44 s | 883 |
| one room + 4 closest by `finder=words` (first version) | 51 | 0.49 s | 1,043 |
| one room + 8 closest by `finder=words` (first version) | 50 | 0.82 s | 1,567 |

This is a retrieval gain, not a notes gain: conventional RAG can use the same finder (`rag:...finder=words`), and
the comparison reports RAG with and without it.

The pre-registered rule (E-61: right answers summed over the seed-2 256K and 1M cuts; adopted only if at least 2
better than the old desk), with the finder as it now stands (the page hint included):

| Desk | 256K (of 41) | 1M (of 73) | Sum | First word p50 at 1M |
|---|---|---|---|---|
| one room + 4 closest by embeddings (the old desk) | 28 | 34 | 62 | 0.36 s |
| one room + 4 closest by `finder=words` | 29 | 49 | 78 | 0.52 s |
| **one room + 6 closest by `finder=words`** | **30** | **55** | **85** | **0.61 s** |
| one room + 8 closest by `finder=words` | 30 | 53 | 83 | 0.71 s |

Adopted: `finder=words`, 6 closest moments (`memory.FINDER`, `memory.CLOSEST`). At 1M it gains in every family
but maths: fact 4 to 8, changed 3 to 10, two-hop 1 to 6, code 5 to 8, lookalike 5 to 10; never-told stays 8 to 9 of
10. Pages now use the design system but still fail: all three run into the 1,200-token limit the yardstick gives
every contender before their footer. These runs shared the GPU with the seed-1 16M run's telling; first-word times
here are for comparing desks with each other only. Next: the same desks on seed 3 (a world never tuned on), then
the held-out runs.
