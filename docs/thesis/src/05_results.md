# System Implementation, Testing and Evaluation {#results}

## Introduction {#results-intro}

> **Chapter 5 at a glance. What CAMR is.** A language model writes text by predicting the next word, and it only knows what it absorbed in training and what is in front of it now. A model small enough for a laptop knows little and can hold only a short history in front of it. CAMR is a memory placed beside the model. Whatever the user tells it is read once by the model, and the notes the model writes to itself while reading (its keys and values) are kept on the Mac's SSD. For each question CAMR opens the one room of notes the question is about and lays it in front of the model, already read. The model itself is never changed.
> **What was tested.** One scripted software project of 2 to 4 million tokens (the Long Haul) with 216 questions graded by rule; Qwen3 models of 1.7, 4 and 8 billion parameters with and without CAMR; a 27-billion-parameter model and Ollama reading CAMR's memory as words; Claude Haiku, Sonnet and Opus 5.5 answering alone as the yardstick; four public suites; four ways of sharing memory; and the time and RAM of every answer as memory grew.
> **What was found.**
> - At 2 million tokens, a 4B model with CAMR answered 29 of 73 questions; Claude Sonnet alone answered 32 and Opus 31. At 3 and 4 million tokens CAMR still answered 29, while Sonnet fell to 13 and then 10.
> - Without CAMR, the same 4B answered 11 to 13 and needed a 15.2 GB process; with CAMR the process needed 5.4 to 7.5 GB once a graphics buffer cache was capped.
> - The first word came in 0.2 to 0.3 seconds with CAMR, against 13 to 105 seconds for Sonnet and Opus.
> - As memory grew from 112 thousand to 2 million tokens, the wait for the first word stayed at about 0.1 s and the RAM at about 4.3 GB (1.7B model); the SSD was held at its 40 GB budget by putting old rooms to sleep.
> - Past 1M tokens most rooms were asleep, so most answers read their room as words; the saved notes bought speed where rooms were awake, not accuracy.
> - CAMR helped most on facts told far back and declined almost every question about things never told. It did not help with joining two facts, or with building a page from a design decided weeks earlier; no contender, Claude included, managed that.
> - Project memory was the best way to share memory (26 of 40); mixing in a second project cost 2 answers.
> **How to read the numbers.** Most results are counts of right answers out of a set of questions, graded by rule. *Right* means the expected answer; for a question about something never told, a decline is right. *Declined* means the model said it did not know something it had been told. *First word* is the wait from the question to the first word of the answer. *Peak RAM* and *footprint* are the memory the whole process used. Every number comes from a dated record in the repository (`v2/records/bench/2026-11-04/`) or from the decision log (E-nn).

This chapter reports what was built, how it was tested, and what the measurements showed, including where the system failed. Section {sec:env} describes the environment and Section {sec:datasets} the data. Section {sec:impl} describes the implementation and the application. Section {sec:testing} reports testing, Sections {sec:vc} and {sec:ai-use} the evidence and the use of AI tools, and Section {sec:eval} the evaluation results, discussion and limitations.

## Implementation Environment {#env}

> **In plain words.** CAMR runs on one Apple-silicon Mac. The model, the memory and the app stay on that Mac; the internet is used to download the models and public datasets once, and, in the benchmarks only, to ask the Claude yardstick.

### Hardware and Deployment Environment

CAMR is a local prototype: a repository, an installer and an application that run on the user's own Mac. Nothing was deployed for public access. Development began on a MacBook Air M4 with 16 GB, the laptop class of the proposal's scope (Section {sec:scope}). From 3 November 2026 every contender was run on a MacBook Pro M5 Pro, and every result of the final engine comes from that machine (Table {tab:hardware}).

Table: {#hardware} Hardware used (from each record's `environment` field)

| Item | Specification | Purpose | Evidence |
|---|---|---|---|
| Evaluation and app machine | MacBook Pro Mac17,9, Apple M5 Pro, 24 GB unified memory, internal SSD, macOS 27.2 | Every Long Haul, suite, reach and speed run; the app | `environment` of the records; E-17 |
| First development machine | MacBook Air M4 (Mac16,12), 16 GB, fanless | Step 0 baselines and the room design (E-14 to E-16) | `records/2026-11-02/`; E-17 |
| Minimum to run | An Apple-silicon Mac; MLX needs one. M1 to M3 Macs and 8 GB Macs were not tested | The installer refuses other machines | `scripts/install.sh` |
| Specialised hardware | None dedicated. MLX uses the chip's integrated graphics processor | The reader's keys and values are read and written inside the process | Table {tab:changes} |
| Network | Model weights and suites downloaded once; the Anthropic API for the yardstick only | Private, offline use (NFR-10) | `bench/claude.py`; `HF_HUB_OFFLINE` |

The records note the power source and the one-minute load when each run started; the 4B's 3M and 4M rerun, for example, ran on AC power at a load of 4.33. One measuring job used the graphics processor at a time, run from a queue that logs each job's start and end (E-35).

### Software, Services and Configuration

Table {tab:software} lists the software and models as tested; their versions come from each record's `environment` and `contender` fields.

Table: {#software} Software and models (versions as tested)

| Component | Version | Role |
|---|---|---|
| Python; NumPy | 3.12.12; 2.5.4 | The engine, the app's engine process, the harness |
| MLX / mlx-lm | 0.32.4 / 0.32.2 | Run the models on the graphics processor and expose the key–value cache (Hannun et al., 2023) |
| Readers (frozen, 4-bit) | `Qwen3-1.7B-4bit`, `Qwen3-4B-Instruct-2507-4bit`, `Qwen3-8B-4bit` (A. Yang et al., 2025) | The engine's contenders |
| Larger local model | `Qwen3.8-27B-4bit` | Reads CAMR's memory as words (its linear-attention layers keep no keys and values) |
| Embedder (frozen) | `Qwen3-Embedding-0.6B-4bit-DWQ` (Zhang et al., 2025) | Every contender |
| Ollama | 0.13.5, `qwen3:1.7b` (Q4_K_M) | The pairing: memory as words |
| Anthropic API | `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`; effort "medium", adaptive thinking | The yardstick, alone |
| SwiftUI app | macOS 14 or later, built with the Swift command-line tools | The native front end (Chat, Code) |
| CAMR v1 as a library | camr 0.4.0 with sqlite-vec 0.1.9 | The baseline contender on the scripted lives |

The engine's settings are constants in the code, recorded in each record's `contender` field: rooms of at most 512 tokens, a join threshold of 0.80, four closest moments re-read, 2 GB of RAM for hot rooms and 40 GB of disk for room files in the benchmarks, the graphics buffer cache capped at 1 GB, and Qwen3's thinking off for every local model. Answers get room by family: 1,200 tokens for a page, 600 for code, 400 for maths and 120 for the rest.

### Deployment and Reproducibility

The engine installs with one script on an Apple-silicon Mac, which checks the machine, creates a Python 3.12 environment, installs the engine and its models, and runs a health check that teaches a throwaway memory two dated facts and asks for one back. A `camr` command then starts the app, the Ollama pairing or the OpenAI-compatible endpoint (E-48). The Mac app is built from its Swift package and starts the engine itself. Every benchmark can be rerun with the commands in Appendix A, and every run writes a dated record to `records/bench/<date>/` after every checkpoint, naming the machine, its load and a hash of the code that made it (`camr_source_sha`). Three limits apply: records written before the rename on the evening of 4 November keep the old field names; no run was repeated for variance; and the Claude yardstick's answers depend on the provider's service on that day.

## Dataset Description {#datasets}

> **In plain words.** The main test is an invented software project, told event by event over 110 working days and then 110 more, with questions about things said weeks earlier. It is fixed by its seed, so anyone can build the same one. Four public test sets add mathematics and long-text reading.

### The Long Haul {#longhaul-data}

The Long Haul is the study's own hard test (E-30). It is one scripted project: a developer building the website and back office of "Mama Njeri's Kitchen", a catering business in Nairobi, over 110 working days. It mixes chat, meetings, decisions, code, documents, logs, a mathematics course and noise. The script for seed 1 has 17,786 events and 2,010,094 tokens (counted with Qwen3-1.7B's tokenizer), from 22 September 2025 to 27 February 2026. For the 3M and 4M cuts it was extended by 110 more working days of noise only, from the same generators with random streams of their own; the first 110 days and every probe were kept exactly as they were, checked event for event (E-39).

Probes are planted early and asked late, and each has one answer a rule can check (Table {tab:families}). One example of an invented rule: the delivery fee is 1% rounded up to the next 5 shillings, at least 10, and a flat 25 for exact multiples of 1,000, so 12,000 gives 25 and 7,321 gives 75. A model cannot know such a rule from training; it can only remember it.

Table: {#families} What the Long Haul plants and asks

| Family | Probes | Planted | Asked | Graded |
|---|---|---|---|---|
| Facts | 400 | Facts at random depths | Far past every window | Exact |
| Changed facts | 80 facts, 160 questions | Each changed 2 to 4 times, with dates | The value now, and the value on a past date | Exact; an old value is stale |
| Two hops | 40 | Two halves, weeks apart | A question that needs both | Exact |
| Corrected maths | 40 problems, 120 questions | A hard problem, a first answer with the tempting wrong method, then a step-by-step correction; some corrections state a rule invented for the project | The same problem; the method with new numbers; the invented rule on a new case | Exact number; the uncorrected method's number is stale |
| The page that grows | 3 | A design system in week 1; the main colour changes on day 61 | "Build the catering page" on day 110 | HTML and CSS checks |
| Code that must fit | 20 | Five helper modules with exact names, units and quirks | New code that calls them | Unit tests run on the answer, in a sandbox |
| Look-alikes | 30 | Two Wanjirus, prices one shilling apart, near-identical repository names | Aimed at one of each pair | Exact |
| Never said | 60 | Nothing | Questions on things never told | A decline is right; a guess is a false memory |

The script is cut at six sizes. At each cut, a checkpoint takes a stratified sample of the probes askable there, 10 from each family (seed 0), each resolved to its right answer at that point (Table {tab:cuts}). Early cuts have fewer questions because some families are not askable yet. The 3M and 4M cuts ask the 2M cut's 73 questions again, so any change in score there is the weight of the longer history, not new questions (E-39).

Table: {#cuts} The cuts and their checkpoints

| Cut | Tokens told | Events told | Last day | Questions |
|---|---|---|---|---|
| 64K | 63,860 | 551 | 7 | 34 |
| 256K | 255,952 | 2,343 | 16 | 40 |
| 1M | 999,988 | 8,760 | 56 | 69 |
| 2M | 1,999,743 | 17,699 | 110 | 73 |
| 3M | 2,999,988 | 26,244 | after day 110 | 73 (the 2M questions) |
| 4M | 4,000,000 | 34,936 | after day 110 | 73 (the 2M questions) |

Every answer receives one of five verdicts (Table {tab:verdicts}). The same answer always gets the same verdict, grading costs nothing, and anyone can grade again from the raw answers kept in each record.

Table: {#verdicts} The verdicts

| Verdict | Meaning |
|---|---|
| right | The expected answer; for a never-told question, a decline that does not then guess |
| wrong | Something else, a look-alike's value, or code or a page that fails its checks |
| stale | A value an update replaced, the uncorrected method's number, or the old main colour |
| declined | Says it does not know, but the answer was told |
| false memory | Answers a question about something never told, or declines and then guesses |

**Synthetic-data risk.** A scripted project cannot establish real-world performance on its own. Each fact is told once or a few times, the questions follow templates, and there is one project. The Long Haul compares memories fairly on such a history, built to be hard in known ways; the public suites and the baseline's public benchmarks are the real-data complement.

### Public Suites from the Hugging Face Hub

Four public suites were loaded, sampled with a seed and graded by their own rules (Table {tab:suites}). They were run on the Claude yardstick and on Ollama, paired and bare; the engine's own MLX contenders were not run on them, because their instructions are the Long Haul's and a suite needs its own (E-36).

Table: {#suites} The public suites as run

| Suite | Source | What it tests | How it was run |
|---|---|---|---|
| BABILong | RMT-team/babilong (Kuratov et al., 2024) | bAbI facts hidden in book text | qa1 to qa5 at 4k, 16k, 64k and 128k tokens, 100 items; the story told in chunks of about 512 tokens, then its question |
| MATH-500 | HuggingFaceH4/MATH-500 (Lightman et al., 2024) | Competition problems | 50 problems of levels 3 to 5, no memory; graded by the last boxed answer's value |
| AIME | MathArena aime_2025 and aime_2026 (Balunović et al., 2025) | 30 problems a year, each a whole number 0 to 999 | 60 problems, no memory; exact |
| HARP pairs | aadityasingh/HARP (Yue et al., 2024) | Problem A and its worked solution as context, then a new problem B of the same subject and level | 60 pairs; memory on: A and its solution told, 30K tokens of Long Haul noise, then B and A asked; memory off: B and A with nothing told |

### Data of the Earlier Stages

The rooms build was developed and judged on three scripted twelve-week lives of invented people (a university student, a dairy-cooperative manager and a software developer), each with about 330 notes and the same 100 questions every week: 45 single facts, 15 updated facts, 10 facts told across two notes, 15 dates and 15 things never told (E-05). Development lives (seed 0) were used for every design choice, and held-out proof lives (seed 1) were run only after the pass marks were written (E-19). The baseline used PopQA, HotpotQA, 2WikiMultiHopQA and GSM8K with fixed samples (seed 13), a store built from supporting and distractor paragraphs only, and a 200-question held-out set for its final claims.

## System Implementation {#impl}

> **In plain words.** The engine is a Python package of a few thousand lines. A moment is read once by the model and its notes are appended to a room file; a question picks one room, reads it from RAM or the SSD, and the model reads only a few lines more before it answers.

### The Engine's Modules

The implementation follows Figures {fig:arch} and {fig:sequence}. Table {tab:modules} lists the engine's main modules with their sizes on 4 November.

Table: {#modules} The engine's main modules (`v2/camr_engine/`)

| Module (lines) | What it does | Requirements |
|---|---|---|
| `rooms.py` (137) | Places a moment by Equation {eq:room}; appends its notes to the room file; fetches a whole room in 1 MB pieces, eight at once, with the cache bypassed; cuts a room file back to its indexed length on opening (E-27) | FR-08, FR-09, IR-03 |
| `notes.py` (101) | Turns tokens into notes and notes into a desk; refuses scaled rotary positions; turns keys to a new position | FR-07, IR-02 |
| `memory.py` (406) | Remember, choose, recall, answer and fade; composes the parts below | FR-07, FR-12 |
| `swap.py` (301) | The tiers: hot rooms in RAM under a budget (least recently used first out), awake rooms on the SSD, sleep past the disk budget, waking | FR-11, FR-13, NFR-04 |
| `vault.py` (613) | One Markdown note per moment; doors between notes; strength fading 5% a day; reads a person's edits back | FR-10 |
| `core.py` (92) | The core: at most 256 tokens of notes tagged `core`, kept in RAM | FR-14 |
| `reach.py` (318) | Sessions over several reaches; one lock per reach folder; the memory switch | FR-15, FR-16, NFR-12 |
| `metrics.py` (169) | One record per answer (Table {tab:metrics}); medians and 90th percentiles | FR-17 |
| `events.py` (104); `live.py` (185) | The event log with attention per written word; the live events the app watches | FR-19, FR-21 |
| `models.py` (245) | Loads the models through MLX, layer by layer; greedy decoding, thinking off; caps the graphics buffer cache | NFR-05, NFR-09 |
| `pair/` (1,039) | The Ollama pairing proxy and the OpenAI-compatible endpoint, with their security checks and metrics | FR-20, IR-06, IR-07 |
| `app/` and `agentic/` | The engine's server and its JSON routes, the Code agent's tools, workspace and approval gate | FR-18, IR-04, IR-05, NFR-11 |
| `bench/` | The Long Haul generator and grader, the local, Ollama and Claude runners, the suites, the reach and RAM runners, the cost ledger | FR-22 to FR-26 |

### Write Path, Read Path and Tiers

Two implementation choices from the rooms build matter for every result. Each room is written as one continuous page, so a new moment is read with its room's earlier moments in view (E-15). A single room is laid on the desk without turning its keys, which cut laying the desk from 55 ms to 15 ms at 2,000 words (E-18). The final engine added three things to that path. Every moment carries its date and day number, as `[YYYY-MM-DD, day N] text`, since the Long Haul asks about days by number. Rooms move between tiers: in the benchmarks, 2 GB of RAM held the hot rooms and 40 GB of disk the awake room files, and at the end of the 2M-token history 920 rooms were awake and 4,471 asleep (E-38). A question whose room is asleep reads that room's moments as words, which costs reading them as plain text would; waking was off in the benchmarks. Finally, the benchmark's questions were read-only: the hot rooms, the least-recently-used clock and the vault strengths were restored after every answer, so that asking never teaches (E-31).

### The Vault, the Core, Reach and the Switch

Every moment is also written to the vault as a Markdown note whose front matter holds its id, day, date, room, reach, strength and links. The vault opens in Obsidian as it is, and a note edited by hand is read again because its file changed. In the benchmarks the core was on but empty, since every moment was told untagged. A `Session` reads several reaches and writes to one; each reach is a folder of its own under `~/.camr/`, locked while a process has it open, and a question picks the best room over every reach it reads. With the switch off, the model answers alone with the same prompt and no notes, and the answer still gets a metrics record, so on and off compare directly.

### Memory for Other Runtimes: the Ollama Pairing

Ollama runs its own model and lets no outside code put keys and values into it, so the engine gives it memory as words. A proxy on 127.0.0.1:11435 speaks Ollama's own API; before a chat is forwarded to the real Ollama, the proxy recalls the closest notes on the last user message and puts them, at most 8 notes and 512 tokens, at the front of that message (E-33). After the answer has streamed back, the exchange is remembered on a background worker. The same code serves an OpenAI-compatible endpoint on 127.0.0.1:11436 in front of Ollama, LM Studio or mlx_lm.server (E-47). Through these doors memory goes in as words; the engine's notes need the engine.

### The Application {#app-impl}

The application described in Section {sec:ui-design} is a Swift package of seven source files (about 1,500 lines) that builds into `CAMR.app`, signed for the Mac it was built on. It starts the engine as a local process with the chosen model (Qwen3 1.7B, 4B or 8B), a free port and a token only it knows, waits for the engine's line saying it holds that port before it sends the token, and then talks to it over the loopback address. Each model has its own memory folder, since notes belong to the model that wrote them. The screenshots in Figures {fig:app-load} to {fig:app-onoff} were captured from the running app with Qwen3 4B and a real memory of 737 rooms.

### The Benchmark Harness and the Contenders {#contenders-section}

The harness drives every contender through the same protocol: it is told the history one event at a time (`tell(text, day)`) and asked each question (`ask(question, max_tokens, family)`). Table {tab:contenders} names the contenders as the records do.

Table: {#contenders} Contenders on the Long Haul

| Name | What it is |
|---|---|
| `engine:qwen3-1.7b`, `engine:qwen3-4b`, `engine:qwen3-8b` | CAMR: one project reach's memory with the vault, the core, the tiers and the metrics on, driven as a `Session` drives it; `+own` gives the 1.7B the engine's own instructions |
| `words:qwen-27b` | CAMR's rooms, chosen the same way, pasted in as text, for the 27B model |
| `bare:<model>` | No memory: the newest part of the history that fits (32K tokens for the 1.7B and 8B, 64K for the 4B), so that its keys and values fit in 24 GB |
| `ollama:qwen3:1.7b`; `ollama-bare:qwen3:1.7b` | Ollama through the pairing (memory as words); plain Ollama with the newest 32,768 tokens |
| `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` | Claude alone: the newest part of the history that fits its one-million-token window, with room for the questions and the reply |

The yardstick runner sends a checkpoint's questions in one streamed request that asks for the answers as JSON, with the history cached where the last request ended. A reply cut off by its own token limit is not graded wrong: the questions it never reached are asked again, alone, with twice the room. No fallback model is ever asked for, so each record names the model that answered. Before each call, its worst-case cost is held in a ledger, and the call is refused if it would pass the night's $60 cap less $2 of headroom.

## Testing {#testing}

> **In plain words.** Automated tests checked each part; benchmark runs checked the whole system against requirements written beforehand; and defects found by the measurements were fixed and the runs repeated. Two requirements were not met and are kept as written.

### Test Strategy

Testing used five levels:

1. **Unit and integration tests.** White-box pytest tests in 45 files cover the rooms, notes, tiers, vault, core, reach, metrics, events, pairing, the app's routes and security, the Code agent, and every part of the benchmark harness (the Long Haul's generator and grader, the runners, the suites and the cost ledger). On 4 November, 730 tests passed.
2. **System tests.** The benchmark runs were judged against the non-functional requirements of Table {tab:nfr}, whose thresholds were written before the runs that tested them (E-19, E-40).
3. **Security tests.** Requests with a foreign host, a foreign origin, no token or a non-JSON body were sent to the engine's server and the proxies.
4. **Deployment test.** The installer and the health check were run, and the Mac app was built and run with the 4B model.
5. **Demonstration.** Chat and Code were used with a real memory, and the screens were captured from the running app (Section {sec:app-impl}).

User acceptance testing and an accessibility audit were not done.

### Test Cases and Results

Table {tab:testcases} gives each test case with its requirement, its expected and actual result and its verdict.

Table: {#testcases} Test cases and results

| Test ID | Traceability | Scenario | Expected result | Actual result and evidence | Verdict |
|---|---|---|---|---|---|
| T-01 | All FR | The automated suite | Every test passes | 730 passed (4 November, before Swarm was removed) | Pass |
| T-02 | NFR-01 | Speed bench, 2,000 words in the room, cache bypassed, five tries | Median first word under 0.5 s | 0.233 s (E-20) | Pass |
| T-03 | NFR-02 | The same bench, notes against words | At least 10 times sooner | 4.6 times (E-20) | Fail (kept) |
| T-04 | NFR-03 | The 1.7B told the whole Long Haul, measured at 1K, 10K and 17.7K moments | First word and RAM do not climb | First word 0.11, 0.15, 0.08 s; RAM 4.26, 4.28, 4.23 GB (E-38) | Pass |
| T-05 | NFR-04 | The same run | Disk within 40 GB; hot rooms within 2 GB | Disk 40.0–40.1 GB, held by sleep; hot rooms 1.95–1.99 GB | Pass |
| T-06 | NFR-05 | The 4B at 3M, with and without the 1 GB cap | Footprint falls; answers unchanged | 19.2 → 7.5 GB; identical verdicts (E-41) | Pass after fix (D-02) |
| T-07 | NFR-06 | The 4B at 3M | Retrieval at most 10% of answer time | Retrieval p50 16 ms of a 0.39 s median answer (4%) | Pass for the 4B |
| T-08 | NFR-07 | Proof lives, week 12: notes against the same desk as words | ≥ 95% of the facts; ≤ 3 extra false memories | 164 against 163 facts; 25 against 24 false memories (E-20) | Pass |
| T-09 | NFR-08 | Never-said questions at every cut | A decline is graded right, a guess false memory | Graded as specified (grading tests); the 4B declined 9 of 10 at 2M and 10 of 10 at 3M and 4M | Pass |
| T-10 | NFR-09 | The 4B's 3M checkpoint run twice | Identical verdicts | 29 of 73 both times, every verdict the same (E-41) | Pass |
| T-11 | NFR-11 | Negative requests to the server and proxies | Only the app's own requests are served | The app's 12 security tests and the pairing's 35 tests, which include its security checks, pass | Pass |
| T-12 | NFR-12 | A second process opens a reach folder | Refused | Refused with `ReachBusy` (reach tests) | Pass |
| T-13 | NFR-14 | The night's yardstick runs | Spend under $60 | $28.71, every call in the ledger | Pass |
| T-14 | NFR-15 | Inspection of the records of 4 November | Machine, load, versions, commit and code hash in each | Present in every record | Pass |
| T-15 | FR-18, FR-19 | The Mac app with Qwen3 4B | Chat and Code work with memory on and off; the weights view moves only with measured events | Figures {fig:app-chat} to {fig:app-onoff} | Pass (demonstration) |
| T-16 | FR-20 | A fact told through the OpenAI-compatible endpoint, asked back through the real Ollama | The fact comes back | "Pilipili", with 187 characters of notes (E-47) | Pass |
| T-17 | FR-22 | The Long Haul built twice from seed 1, and extended | Identical scripts; the first 110 days unchanged by the extension | Generator tests pass; checked event for event (E-39) | Pass |
| T-18 | Users | User acceptance; accessibility audit | | Not run | Not tested |

### Defects Found and Retests

The measurements found six defects in the system or in its measurement (Table {tab:defects}). Each was fixed or bounded, and the affected runs were repeated or reported both ways.

Table: {#defects} Defects found and retests

| ID | Defect and how it was found | Correction | Retest |
|---|---|---|---|
| D-01 | The 1.7B declined facts sitting on its desk at 1M and 2M; diagnosis ruled out retrieval and sleep and found the yardstick's wording (E-37) | The 1.7B is run with both wordings; the others keep the yardstick's, as planned | Both reported (Section {sec:wording}) |
| D-02 | The engine's process held 19.2 GB, not the 5.7 GB the records showed: MLX kept freed graphics buffers up to the whole limit and swap filled (E-40) | The buffer cache capped at 1 GB; every record now logs the process's footprint | 7.5 GB, identical answers (E-41) |
| D-03 | Ollama, bare, BABILong: 58 of 100 answers thrown out as "thinking" with no thinking in them (E-43) | An empty think block is cut off the answer; real thinking is still an error | The 58 resumed (Section {sec:ollama-suites}) |
| D-04 | Ollama, HARP: at the shared 400-token limit, 82 of the bare 1.7B's 120 answers and 95 of the paired one's were cut off mid-working (E-43) | The same room to work in words as Claude has to think (8,192 tokens); the 400-token records kept | Rerun (Section {sec:ollama-suites}) |
| D-05 | Ollama's `qwen3:4b` had become the Thinking build (E-33) | The 4B runs as `qwen3:4b-instruct-2507-q4_K_M` | Pass |
| D-06 | A crash between appending a moment's notes and saving the index would misplace later moments (E-27) | Opening a memory cuts each room file to its indexed length; a test covers it | Pass |

## Version Control and Implementation Evidence {#vc}

The project lives in one Git repository on GitHub (https://github.com/Satasdin/CAMR), which holds the baseline at its root and the engine in `v2/`, with their full histories. The repository is private, so the supervisor and examiners must be given access. The final engine, its records and this report are on the branch `camr-build`. The repository holds the README, the user guide and the decision log; the installer, the scripts and the tests; every benchmark record and the Claude ledger; the Mac app's Swift package; and the generator scripts of this report's figures. `.gitignore` excludes the virtual environment, model weights, datasets and `work/`, where contenders' memories are rebuilt on every run. Each benchmark job of the night committed its records as it finished, so the history shows when each number was made.

## Author Oversight and Use of AI-Assisted Tools {#ai-use}

Claude (Anthropic), used through Claude Code, assisted with this project. Under the student's direction it wrote and revised the engine, the app, the harness and their tests; ran the experiments; and drafted the documentation, including the decision log, the user guide and drafts of this report. The student set the problem, the objectives, the scope and the direction of the work, and made the calls recorded as his own, such as making the engine the project (E-29), pushing the Long Haul past 2 million tokens (E-39), asking for the RAM to be optimised (E-40) and removing Swarm from the app (E-50). The output was checked by running the automated tests, by the records, which name the machine and the code behind every number, and by reading the outputs themselves. Requirements were written before the runs that tested them, and the requirements that were not met are reported as measured. Claude also served, separately, as the yardstick in the benchmarks; that role is unrelated to its role as a tool. The student made the final decisions and takes full responsibility for the work. [[Student to confirm this statement and add the model versions used.]]

## Evaluation Results, Discussion and Limitations {#eval}

> **In plain words.** A 4B model with CAMR answers a long project's questions about as well as Claude Sonnet alone at 2 million tokens, and better past Claude's window, at a fraction of the wait and in a process of 5 to 8 GB. It stays as fast as memory grows. It is weakest at joining facts and at following a design over weeks.

### Results at a Glance {#glance}

Table {tab:scorecard} gives each claim of the study a verdict, with the section that supports it.

Table: {#scorecard} Scorecard: each claim, its evidence and whether it was met

| Claim | Evidence | Result | Verdict |
|---|---|---|---|
| A small model with CAMR answers like a cloud model on a long history | Long Haul at 2M (Section {sec:haul-results}) | 4B + CAMR 29 of 73; Sonnet alone 32, Opus 31, Haiku 10 | Nearly met at 2M |
| Past the cloud model's window, memory wins | Long Haul at 3M and 4M (Section {sec:past-window}) | 4B + CAMR 29 and 29; Sonnet 13 and 10; Haiku 10 and 10 | Met |
| Memory beats the same model without it | Long Haul, every cut | 4B: 25/26/25/29 against 18/14/20/11; 8B: 26/26/24/27 against 15/11/15/11 | Met |
| Lighter than the model reading its own window | Footprint (Section {sec:ram-results}) | 5.4–7.5 GB against 15.2 GB (4B); 8.1–8.8 GB against 13.6 GB (8B) | Met, after the cap (D-02) |
| No slower as memory grows | Speed as memory grows (Section {sec:speed-results}) | First word 0.11 → 0.08 s and RAM 4.26 → 4.23 GB from 112K to 2.01M tokens | Met |
| Faster than the cloud | First word (Section {sec:yardstick}) | 0.2–0.3 s against 13–105 s for Sonnet and Opus | Met |
| Honest about what was never said | Never-said family | 4B declined 9 of 10 at 2M and 10 of 10 past it; Claude 10 of 10 | Met for the 4B; not for the 1.7B with its own wording |
| Memory recovers knowledge, not reasoning | Families at 2M (Section {sec:families}) | Facts 6 of 10 (Sonnet and Opus 4, Haiku 0); two hops 0; the growing page 0 for everyone | Met as predicted |
| Notes and words know the same within a room | Rooms build (Section {sec:rooms-results}) | 164 against 163 facts | Met |
| Notes are at least 10 times sooner than words | Speed bench (Section {sec:rooms-results}) | 4.6 times at 2,000 words | Not met |
| The best reach | Reach (Section {sec:reach-results}) | Project 26 of 40; global 24; session 11 | Project reach |
| Files remembered: PDFs, images, charts, video | Multimodal memory (Section {sec:media-results}) | 29 of 29 planted facts with CAMR, for the vision model and the 4B; 0 for the vision model alone | Met, on a small test |

### The Long Haul: Right Answers as the History Grows {#haul-results}

> **In plain words.** Up to a million tokens Claude Sonnet sees most of the history and answers the most. At 2 million the 4B with CAMR is three answers behind it. Without memory, the same 4B falls to 11.

Table {tab:longhaul} gives every contender's right answers at every cut, with its median wait for the first word and its peak RAM, and Figure {fig:longhaul} plots them as shares, since the cuts ask different numbers of questions.

Table: {#longhaul} Right answers on the Long Haul (questions asked: 34, 40, 69 and 73; 3M and 4M ask the 2M questions)

| Contender | 64K | 256K | 1M | 2M | 3M | 4M | First word p50 | Process RAM |
|---|---|---|---|---|---|---|---|---|
| **CAMR, Qwen3 4B** | **25** | **26** | **25** | **29** | **29** | **29** | 0.21–0.31 s | 7.5 GB (capped, at 3M) |
| Qwen3 4B alone (newest 64K) | 18 | 14 | 20 | 11 | 12 | 13 | 0.32–0.38 s | 15.2 GB |
| CAMR, Qwen3 8B | 26 | 26 | 24 | 27 | | | 0.32–0.54 s | 8.1–8.8 GB |
| Qwen3 8B alone (newest 32K) | 15 | 11 | 15 | 11 | | | 0.22 s | 13.6 GB |
| Qwen 27B, CAMR's memory as words | 24 | 21 | 24 | 27 | | | 2.2–2.4 s | 16–17 GB |
| CAMR, Qwen3 1.7B, its own wording | 19 | 20 | 21 | 21 | | | 0.10–0.14 s | 4.5 GB† |
| CAMR, Qwen3 1.7B, the yardstick's wording | 14 | 20 | 17 | 15 | | | 0.10–0.14 s | 4.5 GB† |
| Qwen3 1.7B alone (newest 32K) | 8 | 13 | 14 | 7 | | | 0.13 s | 7.5 GB† |
| Ollama 1.7B with the pairing (words) | 16 | 17 | 16 | 16 | | | 0.38–0.40 s | 3.3 GB† |
| Ollama 1.7B alone (newest 32K) | 8 | 12 | 10 | 7 | | | | 5.7 GB† |
| Claude Haiku 5.5 alone | 22 | 21 | 17 | 10 | 10 | 10 | 2–43 s | |
| Claude Sonnet 5.5 alone | 28 | 35 | 43 | 32 | 13 | 10 | 13–70 s | |
| Claude Opus 5.5 alone | 24 | 33 | 42 | 31 | | | 19–105 s | |

Process RAM is the process's physical footprint where it was recorded; the figures marked † are peaks measured before the buffer-cache cap (MLX's own peak for the engine, the peak resident memory for Ollama), not process footprints, and may understate the process (Section {sec:ram-results}). The Claude rows have no RAM figure, since Claude runs in the cloud.

![{#longhaul} Share of questions answered right as the history grows. CAMR (cyan) holds its level past 1M tokens; the models alone (amber) and Claude alone (grey, dashed) fall once the history outgrows their windows](figures/ch5/longhaul_share.png){width=15.9}

Four patterns stand out. First, memory roughly doubles what a local model answers once the history outgrows its window: at 2M, the 4B with CAMR answered 29 against 11 for the same model alone, and the 8B 27 against 11. Second, while most of the history fits in Claude's window, Sonnet and Opus answer more: up to 1M, Sonnet answered 28 to 43 and Opus 24 to 42, against CAMR's 25 to 26 at the same cuts, while Haiku (22, 21 and 17) trailed CAMR throughout. Already at 1M the history (counted with Claude's own tokenizer) no longer fitted whole, and Claude's request was cut from the front. Third, at 2M the gap between the 4B with CAMR and Sonnet alone is 3 answers of 73. Fourth, the larger readers did not do better with CAMR's memory than the 4B: the 8B answered 27 at 2M and the 27B, reading the memory as words, 27. On this test the memory, not the reader, sets the ceiling.

Where each answer's room came from matters for reading these results (Table {tab:tiers}). Up to 256K tokens almost every answer read its room as saved notes, from the SSD or from RAM. By 1M tokens the room files had reached their 40 GB disk budget, sleep had put most rooms away as words, and most answers read their room as words: 47 of 69 at 1M, 68 of 73 at 2M, and 71 and 72 of 73 at 3M and 4M. The engine's results past 1M are therefore the results of its memory's organisation (rooms chosen by similarity, the closest moments, dates on every moment) read mostly as words, with the saved notes doing the work only for the rooms that were still awake.

Table: {#tiers} Where the 4B's room came from at each cut (`summary.all.tiers` and `status` in the records)

| Cut | Notes from RAM | Notes from the SSD | Asleep: read as words | Rooms awake / asleep |
|---|---|---|---|---|
| 64K | 6 | 28 | 0 | 237 / 0 |
| 256K | 1 | 34 | 5 | 676 / 61 |
| 1M | 2 | 20 | 47 | 703 / 1,994 |
| 2M | 3 | 2 | 68 | 807 / 4,932 |
| 3M | 0 | 2 | 71 | 987 / 8,368 |
| 4M | 0 | 1 | 72 | 1,152 / 12,669 |

### Past the Window: 3M and 4M {#past-window}

> **In plain words.** Pushed to 3 and 4 million tokens, Claude can only see the last days, which have nothing planted, and it answers little beyond the questions about things never said. CAMR answers exactly as it did at 2 million.

At 3M and 4M the same 73 questions were asked under one and two million more tokens of noise (E-39). The 4B with CAMR answered 29 both times, as at 2M, and declined all 10 never-said questions, with a median first word of 0.31 s. Claude Sonnet answered 13 and then 10, and Haiku 10 and 10: their windows held only the newest days, so they declined almost every question, and what they scored was mostly the never-said questions, which a decline answers right (Sonnet also answered 3 corrected-maths questions at 3M). The 4B alone answered 12 and 13, from the newest 64K tokens. A memory that lives outside the window therefore keeps its answers however long the history grows, while a window, however large, forgets the beginning.

### What Was Answered: Knowledge Against Reasoning {#families}

> **In plain words.** CAMR is best at facts told long ago and at code that must use the project's own helpers. It does not join two facts told weeks apart, and nobody built the page that needed a design from week 1 and a colour change from day 61.

Table {tab:families2m} and Figure {fig:families} break the 2M checkpoint down by family.

Table: {#families2m} Right answers at 2M by family (10 questions each; for "never said", declining is right)

| Family | CAMR 4B | CAMR 1.7B (own wording) | Claude Haiku | Claude Sonnet | Claude Opus |
|---|---|---|---|---|---|
| Facts across the gap | **6** | **6** | 0 | 4 | 4 |
| Changed facts | 3 | 2 | 0 | 5 | 5 |
| Look-alikes | 3 | 3 | 0 | 5 | 5 |
| Corrected maths | 4 | 4 | 0 | 6 | 6 |
| Code that must fit | **4** | 2 | 0 | 2 | 1 |
| Two hops | 0 | 1 | 0 | 0 | 0 |
| Never said | 9 | 3 | 10 | 10 | 10 |
| The page that grows (3) | 0 | 0 | 0 | 0 | 0 |

![{#families} Right answers at 2M tokens by family: CAMR (cyan) against Claude alone (grey, hatched)](figures/ch5/families_2m.png){width=15.9}

The pattern repeats the baseline's finding on public benchmarks (Section {sec:baseline-results}): memory recovers knowledge, not reasoning. CAMR led on facts planted far back (6 of 10 against Claude's 4), because Claude's window no longer held them, and on code that had to call the project's own helpers with their exact names and quirks (4 against 2). Claude led where the answer needs weighing several moments against each other: changed facts, where the newest of several values is right; look-alikes, where two near-identical names must be told apart; and corrected mathematics, where a correction must override a first answer. One room per question seldom holds every version of a changed fact, and a small reader takes the first it sees. Two hops were answered by nobody but once, by the 1.7B, and the growing page was failed by every model, Claude included. It is the hardest probe: it needs the week-1 design system and the day-61 colour change together.

### Larger Readers: 8B and 27B {#bigger}

The 8B with CAMR answered 26, 26, 24 and 27, level with the 4B, with a slower first word (0.32 to 0.54 s) and a larger process (8.1 to 8.8 GB). The 8B alone answered 15, 11, 15 and 11 from its newest 32K tokens, in a 13.6 GB process. The 27B cannot use saved notes, because 48 of its 64 layers keep a running state instead of keys and values (E-26); given the same rooms as words, it answered 24, 21, 24 and 27, at 2.2 to 2.4 s to the first word in a 16 to 17 GB process. A reader twice or about seven times the 4B's size, given the same memory, did not answer more. The memory sets the ceiling here, and the 4B is the best trade of answers against time and RAM on this Mac.

### The 1.7B: Its Wording, Not Its Memory {#wording}

> **In plain words.** The smallest model did badly at first. The cause was not its memory but the instructions: told to answer only from its notes and to say "I don't know" otherwise, it said "I don't know" even when the answer was in front of it.

With the yardstick's instructions, the 1.7B with CAMR scored on facts 2 of 10 at 64K, 5 at 256K, 1 at 1M and 0 at 2M; most of its total came from declining the never-said questions (E-37). Three checks on its own 2M memory found the cause (Table {tab:diagnosis}).

Table: {#diagnosis} Why the 1.7B missed facts at 2M (E-37)

| Check | Finding | Conclusion |
|---|---|---|
| Was the right room chosen? | The room holding the planted fact was chosen for 6 of the 10 facts | Retrieval was not the cause |
| Did sleep lose it? | 37 of 40 recall answers hit an asleep room; waking each room first gave 2 of 40 both ways | Sleep was not the cause |
| Was the fact on the desk? | Yes, sometimes twice (for example "Muthoni Wafula is working off a Lenovo Yoga 7"); the 1.7B still answered "I don't know", even with the same words as plain text in a fresh prompt | The wording was the cause |

With the engine's own wording, written for the scripted lives before any Long Haul result, the same 1.7B answered 19, 20, 21 and 21 against 14, 20, 17 and 15, and 6 of 10 facts at 2M. It also invented more: it declined only 3 of the 10 never-said questions at 2M, against 7 with the yardstick's wording (and, on the same 2M desks read as words, 3 against 8; E-37). The 1.7B's honesty is a property of its wording, not of its memory. The 4B does not have this problem: it keeps the yardstick's wording and is both right and honest. No wording was picked after seeing it work on these questions; the 4B, 8B and 27B kept the yardstick's wording as planned.

### Notes Against Words: What the Tensors Buy {#notes-words}

The same 1.7B, with the same wording, can be given its memory two ways: as notes through the engine, or as words through Ollama and the pairing. As notes it answered 14, 20, 17 and 15; as words, 16, 17, 16 and 16. The first word came three times sooner as notes (0.10 to 0.14 s against 0.38 to 0.40 s), but the notes took 40 GB of disk against 0.1 GB for the pairing's words. On this test the tensors buy speed, not accuracy, though the comparison is clean only at 64K and 256K: at 1M and 2M most of the engine's rooms were asleep, and 41 and 69 of its answers read their room as words (Table {tab:tiers}). The rooms build had found the same within one room, where notes and words knew 164 and 163 facts (Section {sec:rooms-results}).

### Speed as Memory Grows {#speed-results}

> **In plain words.** The wait for the first word did not grow as the memory grew eighteenfold. RAM stayed flat. Only the disk filled, and sleep held it at its budget.

The 1.7B was told the whole Long Haul and measured at 1,000, 10,000 and 17,676 moments, with 5 questions at each point (Table {tab:speed}, Figure {fig:speed}).

Table: {#speed} The wait as memory grows (`engine:qwen3-1.7b`; E-38)

| Moments kept | History | First word, p50 | Retrieval, p50 | Peak RAM | Disk | Rooms awake / asleep |
|---|---|---|---|---|---|---|
| 1,000 | 112K tokens | 0.11 s | 24 ms | 4.26 GB | 14.9 GB | 358 / 0 |
| 10,000 | 1.15M tokens | 0.15 s | 17 ms | 4.28 GB | 40.0 GB | 864 / 2,146 |
| 17,676 (the end) | 2.01M tokens | 0.08 s | 18 ms | 4.23 GB | 40.1 GB | 920 / 4,471 |

![{#speed} The wait, retrieval time, RAM and disk as the 1.7B's memory grows from 1,000 to 17,676 moments](figures/ch5/speed.png){width=15.9}

The first word stays at about 0.1 s because the desk is always one room of at most 512 tokens plus four moments, however large the memory grows. Retrieval, one product of the question with every moment's embedding and one read of a room, took 17 to 24 ms. Reading the history in took about 1,100 tokens a second throughout. The 90th-percentile first word (2 to 5 s) is a question whose room is asleep or whose answer is long, read as words. Rooms not hot were read off the SSD at 6 to 12 GB/s. At the 2M cut, Claude waited 16 to 105 s for its first token (Haiku 15.9 s, Sonnet 53.5 s, Opus 105.2 s).

### RAM: the Cap on the Buffer Cache {#ram-results}

> **In plain words.** The engine first seemed to use 5.7 GB. A closer look showed the whole process holding 19 GB, because the graphics library kept freed buffers. Capping that cache cut the process to 7.5 GB and made it almost twice as fast, with the same answers.

During the 4B's 4M-token run, the process's physical footprint (what Activity Monitor shows) was 19.2 GB, of which only 1.0 GB was resident; the rest sat compressed or in swap, which was full (8.8 of 9.2 GB). The records' "peak RAM" of 5.7 GB was MLX's peak of arrays in use during one answer, so it never saw this. The cause was MLX's cache of freed graphics buffers, which is unbounded up to the graphics limit (about 18 GB here), while a long ingest frees a desk's worth of buffers for every moment (E-40). The cache is now capped at 1 GB when a reader or embedder loads, which changes no computation, only how many freed buffers are kept for reuse. Table {tab:cap} and Figure {fig:ram} give the effect.

Table: {#cap} The 4B at 3M, before and after the 1 GB cap (E-41)

| Measure | No cap | 1 GB cap |
|---|---|---|
| Right answers (of 73) | 29 | 29, every verdict identical |
| Process footprint | 19.2 GB | 7.5 GB |
| Reading the 3M history | 99.5 min (503 tokens/s) | 53 min (938 tokens/s) |
| First word, p50 | 0.37 s | 0.31 s |
| Retrieval, p50 | 20 ms | 16 ms |

![{#ram} Process footprint: the models alone (amber) against CAMR (cyan), before and after the cap](figures/ch5/ram.png){width=15.9}

The 7.5 GB is about what the parts add up to: the 4B's weights, the embedder, the 2 GB pool of hot rooms, the 1 GB cache and Python. At 4M the footprint was 5.4 GB. The 8B, the 27B and the Ollama suite runs were the first measured with the cap. Every run before them (the 1.7B and the 4B up to 2M) ran without it; their scores are unaffected, but their RAM figures are understated.

### Which Reach Works Best {#reach-results}

> **In plain words.** Keeping one memory per project is best. A memory per conversation forgets everything said in other weeks, and mixing two projects in one memory sometimes takes the wrong project's rule.

The 4B with CAMR heard the Long Haul's first 256K tokens four ways and was asked the same 40 questions; the other project was the Long Haul built from seed 2 (Table {tab:reach}, Figure {fig:reach}).

Table: {#reach} Which reach works best (`engine:qwen3-4b`, 256K tokens, 40 questions; E-42)

| Set-up | Right (of 40) | Facts (of 10) | First word p50 | Disk |
|---|---|---|---|---|
| Session: each working week its own memory, asked in the last | 11 | 0 | 0.24 s | 44 GB |
| **Project: every week into one project memory** | **26** | **8** | 0.19 s | 44 GB |
| Global: both projects in one memory | 24 | 8 | 0.19 s | 85 GB |
| Project + global: both read, the closest room wins | 24 | 7 | 0.19 s | 85 GB |

![{#reach} Right answers by reach](figures/ch5/reach.png){width=15.9}

A session's memory holds only its own week, so 10 of its 11 right answers were never-said questions declined. In global memory, two mathematics answers went stale because they took the other project's look-alike rule. When both were read, the other project's room won 7 of the 40 questions and cost exactly 2 answers, a fact and a changed fact, which the 4B declined rather than answer with the other project's facts. Every set-up declined all 10 never-said questions. The app's default therefore stays project reach.

### The Claude Yardstick: Time and Cost {#yardstick}

Claude was only a yardstick: it answered the same questions alone, with no memory. Table {tab:claude} gives what it cost on the Long Haul.

Table: {#claude} The Claude yardstick on the Long Haul (from the records)

| Model | Right, 64K–2M (of 216) | Right, 3M and 4M (of 146) | First token, per request | Cost on the Long Haul |
|---|---|---|---|---|
| Claude Haiku 5.5 | 70 | 20 | 2.2–43.2 s | $1.13 + $0.97 |
| Claude Sonnet 5.5 | 138 | 23 | 12.7–70.0 s | $4.92 + $3.87 |
| Claude Opus 5.5 | 130 | not run | 19.3–105.2 s | $9.86 |

![{#firstword} The wait for the first word as the history grows: CAMR's median (cyan) against the model alone (amber) and Claude's first token per request (grey, dashed); note the logarithmic scale](figures/ch5/first_word.png){width=15.9}

Figure {fig:firstword} sets the waits side by side. For comparison, the 4B with CAMR answered 105 of the same 216 questions from 64K to 2M and 58 of 146 at 3M and 4M. Sonnet answered more within its window, and less beyond it. Opus scored no better than Sonnet on the Long Haul (130 against 138) at twice the price, so it sat out the suites (E-36) and the longer cuts (E-39). Claude was honest: it never invented a never-said fact. Sonnet's and Opus's first token came after 13 s at 64K and up to 105 s at 2M, because each request reads up to a million tokens; the engine's first word came in under a third of a second. Spending for the night, suites included, was $28.71 of the $60 cap, every call logged.

### The Public Suites {#suites-results}

Table {tab:suites-results} gives the public suites. On the three mathematics suites, which test reasoning with nothing to remember, both Claude models were strong; HARP shows how much a worked correction in the context helps a related new problem.

Table: {#suites-results} Right answers on the public suites

| Suite | Claude Haiku 5.5 | Claude Sonnet 5.5 | Ollama 1.7B alone | Ollama 1.7B with the pairing |
|---|---|---|---|---|
| MATH-500, levels 3 to 5 (50) | 44 | 47 | | |
| AIME 2025 and 2026 (60) | 54 | 56 | | |
| HARP pairs, correction told (60) | 55 | 58 | 28 | 34 |
| HARP pairs, nothing told (60) | 48 | 52 | 21 | 21 |
| BABILong qa1–qa5, 4k to 128k (100) | 78 | | 39 | 20 |

For Claude, the told correction raised HARP from 48 to 55 (Haiku) and from 52 to 58 (Sonnet): a worked solution in the context carries to a new problem of the same kind. Haiku answered 78 of 100 BABILong items from 4k to 128k tokens.

### The Ollama Pairing on the Suites {#ollama-suites}

The Ollama 1.7B answers with its thinking off, so on HARP it was given the same room to work in words that Claude has to think in (8,192 tokens; E-43). With that room, a told correction helped it, and the pairing carried the correction better than the model's own window did: with the correction told, the paired model answered 34 of 60 and the bare one 28; with nothing told, both answered 21. At the shared 400-token limit, 82 of the bare model's 120 answers and 95 of the paired one's had been cut off mid-working, and both had scored 10 or 11 either way; those records are kept beside the reruns (D-04).

On BABILong the pairing lost: 20 of 100 against 39 for the bare model reading the newest 32,768 tokens (Table {tab:babilong}). Its questions ask where something is now, which needs the latest of many mentions, and the pairing's 512 tokens of notes hold too few of them (E-43). At 4k and 16k tokens the bare model sees the whole story, and it answered 16 and 10 of 25 against the pairing's 6 and 6; at 64k and 128k both fell. Claude Haiku, reading every story whole, answered 18 to 21 of 25 at every length. The bare runs' 58 answers lost to the empty-thinking check (D-03) were resumed before these counts were taken.

Table: {#babilong} BABILong by story length (25 items each; qa1 to qa5)

| Length | Ollama 1.7B alone (newest 32K) | Ollama 1.7B with the pairing | Claude Haiku 5.5 |
|---|---|---|---|
| 4k | 16 | 6 | 20 |
| 16k | 10 | 6 | 21 |
| 64k | 5 | 3 | 19 |
| 128k | 8 | 5 | 18 |
| All (100) | 39 | 20 | 78 |

Memory as words through the pairing therefore helps where one worked example carries to the next problem, and hurts where the answer is the newest of many similar mentions. The engine's own contenders, which read whole rooms with dates, were not run on these suites (E-36).

### Multimodal Memory {#media-results}

The engine can also remember files (E-44). A PDF becomes one moment per page, an image its caption and the text written in it, and a video a frame every 2 s, each described with its time, by a vision model that turns the file into words once; the moments are then kept like any others, with the file copied into the vault. The multimodal benchmark tells 21 files of Mama Njeri's Kitchen (PDF invoices and menus, photographed receipts and notices, charts and short whiteboard videos) among about 100,000 tokens of the Long Haul's own events, all in the first 60,000 tokens, and then asks 37 questions graded by the Long Haul's rules: 29 about facts planted in the files, by kind of file, and 8 never-said questions where declining is right. The contenders are Qwen2.5-VL-3B with CAMR, alone with its newest 32K tokens, and with the file itself in the prompt as an upper bound; Qwen3 4B with CAMR and alone, reading the vision model's words; and Ollama's `qwen2.5vl:3b`, paired and bare.

Table {tab:media} gives the results for seed 1 by kind of file, with each contender's total on a second draw of files and questions (seed 2), from the records `*-media-*.json` of 4 November.

Table: {#media} Multimodal memory: right answers by kind of file (seed 1: 29 planted facts and 8 never-said questions; seed 2: the same counts)

| Contender | PDF (8) | Image (9) | Chart (6) | Video (6) | Never said (8) | Seed 1 (37) | Seed 2 (37) | First word p50 | Process RAM |
|---|---|---|---|---|---|---|---|---|---|
| **Qwen3 4B with CAMR, reading the vision model's words** | **8** | **9** | **6** | **6** | **8** | **37** | **35** | 0.34 s | 7.3 GB |
| Qwen3 4B alone (newest 64K) | 1 | 5 | 3 | 1 | 7 | 17 | 18 | 0.32 s | 12.4 GB |
| Qwen2.5-VL-3B with CAMR | 8 | 9 | 6 | 6 | 4 | 33 | 31 | 0.21 s | 5.1 GB |
| Qwen2.5-VL-3B with CAMR, looking at the image again | 8 | 9 | 6 | 6 | 3 | 32 | | 0.80 s | 8.7 GB |
| Qwen2.5-VL-3B with the file in the prompt (upper bound) | 8 | 9 | 6 | 6 | 5 | 34 | 33 | 1.23 s | 4.4 GB |
| Qwen2.5-VL-3B alone (newest 32K) | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0.14 s | 6.3 GB |
| Ollama `qwen2.5vl:3b` with the pairing (words) | 8 | 9 | 6 | 6 | 5 | 34 | 33 | 0.22 s | 1.9 GB† |
| Ollama `qwen2.5vl:3b` alone (newest 32K) | 0 | 0 | 0 | 0 | 5 | 5 | 2 | | 1.9 GB† |
| Ollama `gemma3:4b` with the pairing (words) | 8 | 7 | 6 | 5 | 2 | 28 | | 0.36 s | 1.9 GB† |
| Ollama `gemma3:4b` alone (newest 32K) | 0 | 0 | 0 | 1 | 4 | 5 | | | 1.9 GB† |

With CAMR, every planted fact from every kind of file was recalled on seed 1, at least 40,000 tokens after the file was told, by the vision model and by the text-only 4B: 29 of 29 each, and 27 to 28 of 29 on seed 2. The 4B with CAMR answered all 37 on seed 1 and 35 on seed 2, declining every never-said question, and beat the vision model holding the file in its prompt (34 and 33) at under a third of its wait. The models alone recalled almost nothing: by the questions, the files had left their windows. Ollama's vision model, given memory as words through the pairing, did as well as the engine's vision model (34 and 33), in the smallest process. A second vision model, Ollama's Gemma 3 4B, described the files itself and, through the pairing, recalled 26 of the 29 facts against 1 alone, but invented answers to 6 of the 8 never-said questions. Looking at the image again added nothing on this set and cost nearly four times the wait. The vision models' weakness was honesty, not recall: with memory they invented answers to 3 to 5 of the 8 never-said questions, where the 4B invented none. († Ollama's own peak resident memory, not a process footprint.)

### Development Evidence: the Rooms Build on Scripted Lives {#rooms-results}

> **In plain words.** Before the final engine, its first build was tested on three invented twelve-week lives. Its notes answered as well as the words they came from, it stayed as fast in week 12 as in week 1, and it did errands three times as well as the baseline. It also made things up about what it was never told.

The rooms build stored one room of notes per question and was judged on the three held-out lives, with pass marks written before the runs (E-19, E-20). Its design came from a negative finding: notes written one moment at a time, then laid side by side, lost the thread; with 30 unrelated moments beside the right one, the reader found 2 of 46 facts from such notes against 32 from the words (E-15). Writing each room as one page fixed this within a room, and Table {tab:desks} shows the desk that won.

Table: {#desks} Desks compared on the development lives at day 83, MacBook Air (E-16)

| Desk | Knows (of 255) | First word |
|---|---|---|
| Words, 3 rooms | 144 | 1.65 s |
| Notes, 3 rooms, plus 4 closest moments | 142 | 0.35 s |
| 4 closest moments as words, no room | 135 | 0.45 s |
| Notes, 1 room | 120 | 0.17 s |
| **Notes, 1 room, plus 4 closest moments** | **158** | **0.36 s** |

On the proof lives at week 12 (Table {tab:lives}) the rooms build was level with the baseline on the same 1.7B reader, at half the wait and 0.4 GB less RAM, and without the baseline's hand-written rules. Paired over the 255 told facts, 138 were known by both, 26 by the rooms build alone and 28 by the baseline alone. Its notes gave the same answer as the words on 3,483 of 3,600 questions. Its wait stayed at 0.064 to 0.072 s in every week of every life while its notes on the SSD grew from 82 MB to 963 MB, and its peak RAM (as MLX reports it) stayed between 1.65 and 1.83 GB.

Table: {#lives} The proof lives at week 12, three lives added (E-20)

| Contender | Knows (of 255) | False memories (of 45) | First word | Peak RAM |
|---|---|---|---|---|
| 1.7B alone | 0 | 0 | 0.05 s | 1.31 GB |
| Perfect reader (every note pasted in) | 90 | 17 | 1.90 s, climbing | 2.77 GB |
| CAMR v1 (baseline), 1.7B | 166 | 29 | 0.15 s | 2.24 GB |
| CAMR v1 (baseline), 4B | 208 | 10 | 0.35 s | 3.58 GB |
| **Rooms build, 1.7B** | **164** | **25** | **0.07 s** | **1.82 GB** |
| Rooms build, the same memory read as words | 163 | 24 | 0.09 s | 2.20 GB |

The errands separated the memories most (Table {tab:errands}). Each quiz question became an errand whose tool needs that exact fact; "Where does my vet live?" became "Book me a ride to my vet's home", which calls `book_ride(destination)`. The rooms build did three times as many errands right as the baseline, although the two were level on the quiz, because the baseline's gates were tuned for questions and a request falls past them, whereas the rooms build opens the closest room however the task is worded (E-25). No memory ever asked when it did not know: the rooms build made up 42 of the 45 never-told errands. That was the clearest weakness of the first build; the final engine's 4B declined 9 to 10 of 10 never-said questions on the Long Haul.

Table: {#errands} Errands on the proof lives, last day, 1.7B reader (E-25)

| Memory | Right (of 255) | Old value | Made up (of 45) | Asked | First word |
|---|---|---|---|---|---|
| None | 1 | 0 | 44 | 0 | 0.15 s |
| CAMR v1 (baseline) | 40 | 6 | 45 | 0 | 0.16 s |
| **Rooms build** | **122** | 16 | 42 | 0 | 0.19 s |

The speed bench measured how the wait grows with the memory on the desk (Table {tab:speedbench}). Notes met the 0.5 s mark at 2,000 words, but were 4.6 times sooner than words rather than the 10 times required by NFR-02. The 10 times had been estimated on the MacBook Air, which read text about eight times more slowly than the Pro (about 800 against 6,600 tokens a second; E-17). Notes skip the reading but still pay for the SSD read and the copy into graphics memory, so their head start grows with the room.

Table: {#speedbench} Time to the first word by memory on the desk, median of 5 (E-20)

| Words in the room | Notes read | Notes | Words | Notes sooner by |
|---|---|---|---|---|
| 253 | 75 MB | 0.078 s | 0.148 s | 1.9× |
| 1,002 | 294 MB | 0.116 s | 0.431 s | 3.7× |
| 2,006 | 588 MB | 0.233 s | 1.080 s | 4.6× |
| 3,007 | 894 MB | 0.278 s | 1.605 s | 5.8× |

The room size was tuned on the development lives for the most facts known (E-18): rooms of up to 512 tokens with a join threshold of 0.80 (208 tokens on average) and four moments re-read knew 164 of 255 facts; rooms of up to 1,024 and 2,048 tokens knew fewer at every setting tried (131 to 158). A small, fixed desk is best for a small reader, which agrees with the baseline, where 128 tokens was best for a 0.5B reader on facts.

### The Baseline, CAMR v1, on Public Benchmarks {#baseline-results}

> **In plain words.** The first version of CAMR, which kept text notes, showed on public test sets that a small model with memory can match a cloud model on facts, but not on reasoning.

The baseline was evaluated before the engine existed, on CPU-only machines with Kimi K3 as the cloud ceiling. Its results still hold for the baseline and are the real-data complement to the scripted tests above; they are not results of the final engine. Table {tab:baseline} summarises them.

Table: {#baseline} The baseline's main results on public benchmarks (CAMR v1)

| Claim | Evidence | Result | Verdict |
|---|---|---|---|
| Long-tail facts: a small model with memory matches the cloud model | 22-model sweep; PopQA | 20 of 22 models reach or beat Kimi K3 closed-book (66.7%) with memory | Met |
| Multi-hop: memory closes part of the gap | HotpotQA, 200 held-out questions | 3B + CAMR v1 54.0% against Kimi K3 51.8%; the 0.5B gains 23 points but stays far below | Met from 3B |
| The second hop found without a graph | 2WikiMultiHopQA retrieval, 500 questions | Full-support recall 35.8% → 78.4% at the same budget | Met |
| Reasoning gaps closed by memory | GSM8K | No: a residual of 83.3 points; worked examples hurt the 0.5B | Not met |
| Few wrong facts stated | Held-out PopQA, 200, judged | 3.0% wrong stated (Kimi K3 alone 31.5%), 60.5% right (Kimi 67.5%) | Met, at a cost in coverage |
| Memory beats fine-tuning on facts | The same documents | 71.7% against 13.3% | Met |
| Retrieval at most 10% of answer time | Device profile | 56% for the 0.5B under contention; met only from 1.5B | Not met for 0.5B |

Three findings carried into the engine's design. Memory helps when the gap is knowledge and not when it is reasoning, which the Long Haul's families confirmed. More text distracts a small reader, so the budget should be small, which the room size confirmed. And recency and importance weighting lowered full-support recall on independent questions (by 1.2 points on 2WikiMultiHopQA and 5.4 on HotpotQA), so the engine chooses rooms by similarity alone.

### What Failed, and Why {#failures}

Table {tab:failures} lists every weakness the measurements found, including those that were fixed, because they show how the system failed before the fix.

Table: {#failures} Weaknesses found

| Weakness | Evidence | Cause | Status |
|---|---|---|---|
| Two hops are not joined | 0 of 10 at 2M (4B) | One room per question seldom holds both halves, and the reader does not join rooms | Open: reading several rooms together |
| The growing page is never built | 0 of 3 for every model at 2M | It needs the week-1 design and the day-61 change together | Open, for everyone |
| Changed facts and look-alikes trail Claude | 3 against 5 at 2M | The newest of several values must be weighed against the others | Open |
| The 1.7B's honesty depends on its wording | Never said 3 of 10 at 2M (own wording) against 7 (yardstick's) | A small reader follows its instructions too literally either way | Bounded: both reported; the 4B is honest |
| RAM was understated | 19.2 GB footprint against 5.7 GB reported (E-40) | MLX's unbounded buffer cache | Fixed: 1 GB cap, footprint logged |
| Notes are 10 times sooner than words | 4.6 times (E-20) | The mark was set on a slower machine | Not met, kept |
| Notes are large | The room files reached the 40 GB budget by 1M tokens and were held there by sleep; 147,456 bytes per token for the 4B | Keys and values are about 29,000 times their text for the 1.7B, and more for the 4B | Bounded by sleep; distilling not built |
| Swarm was not measured | No benchmark | Built late, then removed from the app (E-50) | Removed |

### Limitations, Delimitations and Threats to Validity {#limitations}

Limitations are weaknesses of the evidence; each is stated with its likely effect.

1. **A scripted test.** The Long Haul is one invented project, fixed by its seed and built to be hard in known ways. It is not a sample of real work, and its results compare memories fairly on such a history but do not show how CAMR would serve a real user.
2. **Small samples.** Each checkpoint asks 34 to 73 questions, 10 per family (3 for the page), so a difference of one or two answers is within noise; the 3-answer gap at 2M between CAMR and Sonnet is not a reliable ranking. No run was repeated for variance; only the 4B's 3M checkpoint was run twice, with identical verdicts.
3. **Claude is a yardstick, not an opponent.** Claude answered with no memory, reading the newest part of the history that fits its window. A cloud model with its own memory would do better past its window; the comparison shows what a window alone does, not the best a cloud service could do.
4. **RAM before the cap is understated.** The 1.7B's and the 4B's RAM figures up to 2M were measured as MLX's peak, before the buffer-cache cap; the process held more (E-40). Their scores are unaffected.
5. **One machine.** Every Long Haul, suite and speed number was measured on one MacBook Pro M5 Pro with 24 GB (the desk design on the MacBook Air, and the baseline on CPU-only machines); answers also differ slightly between chips (158 facts on the Air and 164 on the Pro for the same design; E-17).
6. **Grading by rule.** A rule can miss a right answer worded in an unexpected way. Every raw answer is kept in the records, so any verdict can be checked by hand, but no hand audit was done for this report.
7. **What was not measured.** The engine's own contenders were not run on the public suites (E-36); LongMemEval and two further suites have loaders but no runs; the Code agent has no benchmark; no user study and no accessibility audit were done; the app's screenshots come from one session.

Delimitations are boundaries chosen for the study: Apple-silicon Macs only; English text; frozen, quantised open models; no fine-tuning; memory on the device, with the cloud only as a yardstick. Threats to validity: internally, every contender read the same instructions and the same questions, and the one wording change (the 1.7B's) is reported both ways; externally, the results hold for one scripted project, one Mac and the models named.
