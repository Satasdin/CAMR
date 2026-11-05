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

This chapter reports how the design of Chapter 4 was implemented, made available on the Mac, tested and evaluated, including where the system failed. CAMR is a hybrid project: an AI artefact evaluated by experiment and an application used through its interface. The chapter therefore follows the AI and machine-learning route of the department's guidelines, with the datasets described before the implementation and the evaluation, and adds the application's modules and user workflows from the software route. Section {sec:env} describes the environment and Section {sec:datasets} the data and its preparation. Section {sec:impl} describes the implementation of the engine, the assistant and the application, with the application's screens. Section {sec:testing} reports the test strategy, the test cases, and the defects and retests. Sections {sec:vc} and {sec:ai-use} give the implementation evidence and the use of AI tools. Section {sec:eval} presents the evaluation results, and Section {sec:discussion} discusses them objective by objective, with the failures and the limitations. Conclusions and recommendations are left to Chapter 6.

## Implementation Environment {#env}

> **In plain words.** CAMR runs on one Apple-silicon Mac. The model, the memory and the app stay on that Mac; the internet is used to download the models and public datasets once, and, in the benchmarks only, to ask the Claude yardstick.

### Hardware and Deployment Environment

CAMR is a local prototype: a repository, an installer and an application that run on the user's own Mac. Nothing was deployed for public access. Development began on a MacBook Air M4 with 16 GB, the laptop class of the proposal's scope (Section {sec:scope}). From 3 November 2026 every contender was run on a MacBook Pro M5 Pro, and every result of the final engine comes from that machine (Table {tab:hardware}).

Table: {#hardware} Implementation environment and minimum requirements (from each record's `environment` field)

| Item or layer | Minimum tested specification or version | Purpose and justification | Evidence or source |
|---|---|---|---|
| Evaluation and app machine | MacBook Pro Mac17,9, Apple M5 Pro, 24 GB unified memory, internal SSD, macOS 27.2 | Every Long Haul, suite, reach, speed, multimodal and Code run, and the app; 24 GB holds the 8B reader, the embedder and the vision model together | `environment` of the records; E-17 |
| First development machine | MacBook Air M4 (Mac16,12), 16 GB, fanless | The rooms build's baselines and room design (E-14 to E-16); the laptop class of the proposal | `records/2026-11-02/`; E-17 |
| Minimum to run | An Apple-silicon Mac with 16 GB for the 1.7B reader (tested on the Air); 24 GB for the 4B and 8B readers and the vision model (tested on the Pro). M1 to M3 Macs and 8 GB Macs were not tested | MLX runs only on Apple silicon; the installer refuses other machines | `scripts/install.sh`; the records |
| Storage | The internal SSD; free space for the models (about 1 to 5 GB each) and a disk budget per shelf (8 GB by default in the app, 40 GB in the benchmarks) | Room files are read from the SSD with the cache bypassed; the budget bounds what memory may take | `swap.py`; E-54 |
| Specialised hardware | None dedicated. MLX uses the chip's integrated graphics processor | The reader's keys and values are read and written inside the process | Table {tab:changes} |
| Network | Model weights and suites downloaded once; Wikipedia when the user asks for research; the Anthropic API for the yardstick only | Private, offline use (NFR-10) | `bench/claude.py`; `assistant.py`; `HF_HUB_OFFLINE` |

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
| Vision model (frozen, 4-bit) | `Qwen3-VL-4B-Thinking-4bit`, through mlx-vlm | The app's eyes: describes images and video frames once, reasoning before it describes (E-57) |
| Embedder (frozen) | `Qwen3-Embedding-0.6B-4bit-DWQ` (Zhang et al., 2025) | Every contender |
| Ollama | 0.13.5, `qwen3:1.7b` (Q4_K_M) | The pairing: memory as words |
| Anthropic API | `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`; effort "medium", adaptive thinking | The yardstick, alone |
| SwiftUI app | macOS 14 or later, built with the Swift command-line tools | The native front end (Chat, Code) |
| CAMR v1 as a library | camr 0.4.0 with sqlite-vec 0.1.9 | The baseline contender on the scripted lives |
| Wikipedia | The public MediaWiki API over HTTPS | Research: one search and one page per question, read as data (E-55) |

The engine's settings are constants in the code, recorded in each record's `contender` field: rooms of at most 512 tokens, a join threshold of 0.80, four closest moments re-read, 2 GB of RAM for hot rooms and 40 GB of disk for room files in the benchmarks, the graphics buffer cache capped at 1 GB, and Qwen3's thinking off for every local model in the benchmarks. In the app, rooms are stored at 8 bits by default and each shelf has an 8 GB disk budget (E-54), and a thinking build may think before it answers. Answers get room by family: 1,200 tokens for a page, 600 for code, 400 for maths and 120 for the rest.

### Deployment and Reproducibility

The engine installs with one script on an Apple-silicon Mac, which checks the machine, creates a Python 3.12 environment, installs the engine and its models, and runs a health check that teaches a throwaway memory two dated facts and asks for one back. A `camr` command then starts the app, the Ollama pairing or the OpenAI-compatible endpoint (E-48). The Mac app is built from its Swift package into `CAMR.app`, which is copied into the Mac's Applications folder, appears there and in Launchpad like any other application, and starts the engine itself. Every benchmark can be rerun with the commands in Appendix A, and every run writes a dated record to `records/bench/<date>/` after every checkpoint, naming the machine, its load and a hash of the code that made it (`camr_source_sha`). Three limits apply: records written before the rename on the evening of 4 November keep the old field names; no run was repeated for variance; and the Claude yardstick's answers depend on the provider's service on that day.

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

Every answer receives one of five verdicts (Table {tab:verdicts}). The same answer always gets the same verdict, grading costs nothing, and anyone can grade again from the raw answers kept in each record. A contender's score at a cut is its accuracy, the share of the cut's questions graded right (Equation {eq:accuracy}); the tables give the counts R and Q, and Figure {fig:longhaul} the shares.

$$\text{accuracy}_c = \frac{R_c}{Q_c}$$ {#accuracy} [Accuracy at a cut]

In Equation {eq:accuracy}, \(R_c\) is the number of answers graded right at cut \(c\) and \(Q_c\) the number of questions asked there (34, 40, 69 or 73).

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

### Data Preparation and Partitioning {#data-prep-5}

The raw data became model input in four steps, the same for every contender.

1. **Dating.** Each Long Haul event was turned into one moment that carries its date and day number, as `[YYYY-MM-DD, day N] text` (DR-04), because the questions ask about days by number. For example, the event "Wanjiru says the delivery van is booked for Thursday" told on day 37 becomes `[2025-11-11, day 37] Wanjiru says the delivery van is booked for Thursday`.
2. **Counting and cutting.** Tokens were counted with Qwen3-1.7B's tokenizer, and the script was cut at fixed token counts (Table {tab:cuts}), so a cut is the same text for every contender.
3. **Chunking for the suites.** BABILong stories were told in chunks of about 512 tokens, then the question was asked; HARP's problem A and its worked solution were told as one moment, followed by 30,000 tokens of Long Haul noise.
4. **Files to words.** In the multimodal test and the app, a PDF became one moment per page of its text, an image its description and the text written in it, and a video one described frame every 2 seconds with its time (E-44); each such moment is marked as from a file.

There was no training, so partitioning concerns the settings and the questions. Settings were chosen on development data only and then frozen: the room size and the desk on the development lives (seed 0), the baseline's budget and gate on validation questions. The held-out data, the proof lives (seed 1), the Long Haul and the suites, were run only after the settings and the instructions were fixed (E-19, E-32). Asking was read-only, so no question could teach the memory the answer to a later one (E-31). Duplicate and paraphrased probes within the Long Haul are of one script and one seed, so they are always in the same partition.

## System Implementation {#impl}

> **In plain words.** The engine is a Python package of a few thousand lines. A moment is read once by the model and its notes are appended to a room file; a question picks one room, reads it from RAM or the SSD, and the model reads only a few lines more before it answers.

### The Engine's Modules

The implementation follows Figures {fig:arch} and {fig:sequence}. Table {tab:modules} lists the engine's main modules with their sizes on 5 November.

Table: {#modules} The engine's main modules (`v2/camr_engine/`)

| Module (lines) | What it does | Requirements |
|---|---|---|
| `rooms.py` (182) | Places a moment by Equation {eq:room}; appends its notes to the room file; fetches a whole room in 1 MB pieces, eight at once, with the cache bypassed; cuts a room file back to its indexed length on opening (E-27) | FR-08, FR-09, IR-03 |
| `notes.py` (157) | Turns tokens into notes and notes into a desk; refuses scaled rotary positions; turns keys to a new position | FR-07, IR-02 |
| `memory.py` (411) | Remember, choose, recall, answer and fade; composes the parts below | FR-07, FR-12 |
| `swap.py` (307) | The tiers: hot rooms in RAM under a budget (least recently used first out), awake rooms on the SSD, sleep past the disk budget, waking | FR-11, FR-13, NFR-04 |
| `vault.py` (613) | One Markdown note per moment; doors between notes; strength fading 5% a day; reads a person's edits back | FR-10 |
| `core.py` (92) | The core: at most 256 tokens of notes tagged `core`, kept in RAM | FR-14 |
| `reach.py` (318) | Sessions over several reaches; one lock per reach folder; the memory switch | FR-15, FR-16, NFR-12 |
| `metrics.py` (169) | One record per answer (Table {tab:metrics}); medians and 90th percentiles | FR-17 |
| `events.py` (108); `live.py` (186) | The event log with attention per written word; the live events the app watches | FR-19, FR-21 |
| `models.py` (258) | Loads the models through MLX, layer by layer; greedy decoding, thinking off; caps the graphics buffer cache | NFR-05, NFR-09 |
| `pair/` (1,053) | The Ollama pairing proxy and the OpenAI-compatible endpoint, with their security checks and metrics | FR-20, IR-06, IR-07 |
| `shelves.py` (154) | The four shelves, the Auto sorter and the warm-up | FR-31 |
| `assistant.py` (132); `revise.py` (93) | The router, Wikipedia research, thinking; SAME, UPDATE or NEW before a moment is kept | FR-27, FR-28, FR-30 |
| `media.py` (333); `shrink.py` (213) | Files into words (PDF pages, images and video frames through the vision model); rooms stored at 8 or 4 bits | FR-29, NFR-04 |
| `app/` and `agentic/` | The engine's server and its JSON routes, the Code agent's tools, workspace and approval gate | FR-18, IR-04, IR-05, NFR-11 |
| `bench/` | The Long Haul generator and grader, the local, Ollama and Claude runners, the suites, the reach and RAM runners, the cost ledger | FR-22 to FR-26 |



### Write Path, Read Path and Tiers

Every choice of memory rests on one closeness measure, the cosine of two embeddings (Equation {eq:closeness}). Embeddings are stored as unit vectors, so the cosine is a single dot product, and a question is compared with every moment in one matrix product; the moment with the highest closeness gives the room that is read, and a new moment joins a room only when its closeness to a moment there is at least 0.80 (Equation {eq:room}).

$$s(a,b) = \hat{e}_a \cdot \hat{e}_b = \cos\theta_{ab}, \qquad m^{*} = \underset{m}{\mathrm{arg\,max}}\ s(q,m)$$ {#closeness} [Closeness of two moments, and the moment a question reads]

Here \(\hat{e}_a\) and \(\hat{e}_b\) are the unit embeddings of moments \(a\) and \(b\), \(q\) is the question and \(m\) ranges over every moment kept. The notes a room holds take the size given by Equation {eq:notes}, which is Equation {eq:bytes} multiplied by the room's tokens.

$$S_{\text{notes}} = n \times L \times 2 \times H_{kv} \times d_h \times b$$ {#notes} [Size of a room's notes]

For \(n\) tokens, \(L\) layers, \(H_{kv}\) key–value heads of size \(d_h\) and \(b\) bytes per value (2 at 16 bits), a full 512-token room is 512 × 28 × 2 × 8 × 128 × 2 = 58.7 MB on the 1.7B and 512 × 36 × 2 × 8 × 128 × 2 = 75.5 MB on the 4B and 8B.

Two implementation choices from the rooms build matter for every result. Each room is written as one continuous page, so a new moment is read with its room's earlier moments in view (E-15). A single room is laid on the desk without turning its keys, which cut laying the desk from 55 ms to 15 ms at 2,000 words (E-18). The final engine added three things to that path. Every moment carries its date and day number, as `[YYYY-MM-DD, day N] text`, since the Long Haul asks about days by number. Rooms move between tiers: in the benchmarks, 2 GB of RAM held the hot rooms and 40 GB of disk the awake room files, and at the end of the 2M-token history 920 rooms were awake and 4,471 asleep (E-38). The disk budget is kept by the rule of Equation {eq:budget}: while the awake room files outgrow the budget, the weakest room goes to sleep, ties going to the room used least recently.

A question whose room is asleep reads that room's moments as words, which costs reading them as plain text would; waking was off in the benchmarks. Finally, the benchmark's questions were read-only: the hot rooms, the least-recently-used clock and the vault strengths were restored after every answer, so that asking never teaches (E-31).

### Model Selection and Configuration {#models-section}

No model was trained or fine-tuned; the study's claim is about a memory beside a frozen model (Section {sec:scope}). The readers were selected for what the engine needs and what the Mac holds. A reader must keep keys and values at every layer with plain rotary positions, so that its notes can be saved and laid back (IR-02); the Qwen3 family meets this, and its 1.7B, 4B and 8B builds span the sizes a 24 GB Mac can run with the embedder beside them. Qwen3.8-27B was kept as a larger reader of the memory as words, because most of its layers keep a running state instead of keys and values (E-26). One embedder, Qwen3-Embedding-0.6B, serves every contender, so that every memory chooses rooms by the same closeness (E-02). The vision model was chosen for the app by the same rule as the readers, a frozen 4-bit model that runs in MLX, and as a reasoning model, Qwen3-VL-4B-Thinking, whose thinking is removed before its description is kept (E-57). The multimodal benchmark had already been run with Qwen2.5-VL-3B and Gemma 3 (Section {sec:media-results}).

The engine's settings were fixed before the held-out runs: rooms of at most 512 tokens with a join threshold of 0.80 and four closest moments re-read, chosen on the development lives (E-18), and the yardstick's instructions for every contender, with the 1.7B also run under the engine's own wording once the cause of its declines was found (E-37). In the benchmarks every local model decoded greedily with thinking off (NFR-09). In the app, a hybrid thinking build (Qwen3 1.7B and 8B) may think before a general answer, within 2,400 tokens of thinking and 700 of answer, while the 4B Instruct build answers directly. Rooms are stored at 8 bits by default in the app, since 8-bit rooms answered as 16-bit rooms did at about half the disk (Section {sec:bits-results}).

### The Vault, the Core, Reach and the Switch

Every moment is also written to the vault as a Markdown note whose front matter holds its id, day, date, room, reach, strength and links. The vault opens in Obsidian as it is, and a note edited by hand is read again because its file changed. In the benchmarks the core was on but empty, since every moment was told untagged. A `Session` reads several reaches and writes to one; each reach is a folder of its own under `~/.camr/`, locked while a process has it open, and a question picks the best room over every reach it reads. With the switch off, the model answers alone with the same prompt and no notes, and the answer still gets a metrics record, so on and off compare directly.

### The Assistant: Routing, Research, Files and Revision {#assistant-impl}

The assistant of Section {sec:assistant-design} was implemented in `assistant.py`, `revise.py`, `shelves.py` and the chat route of the engine's server. The router asks the reader for at most three tokens with no live events, so its word is never shown or measured as an answer; before asking, the five closest notes are checked for a name the question carries, with possessives removed, and a match goes to memory outright (E-55). A memory question also reads the closest moment of every other shelf whose closeness is within 0.12 of the best, so a moment filed on another shelf is not lost to a crowded one. A general question is answered with the last six turns of the conversation; a thinking model's reasoning is split from its answer and shown folded. Research uses Wikipedia's search and page-text API with a fixed timeout and a named user agent; the page is cut to 6,000 characters, its angle brackets are neutralised so that it cannot close its markers, and it is placed in the user's turn between `<source>` markers; links in answers are kept only when they are `http` or `https`. Attachments are read by `media.py`: PDF and text pages directly, images and video frames through the vision model, which is downloaded the first time a picture needs it. Revision compares a new moment only with moments of the same source, decided by the vault note's tags (`user`, `file` or `web`) and never by the words; a pair closer than 0.78 is judged in one word, and a moment is left out as SAME only when the pair is also at least 0.95 close and the word is exactly SAME (E-56). Conversations are saved one file per chat under the memory's folder, under identifiers checked against a fixed pattern before any file is opened.

### The Application: Modules, Integration and User Workflows {#app-impl}

The application is a Swift package of eight source files (2,122 lines) that builds into `CAMR.app`, signed for the Mac it was built on and installed in the Applications folder. Its modules are the engine process (`Engine.swift`), Chat (`Chat.swift`), Code (`Code.swift`), the weights view (`Weights.swift`), the settings window, the theme, the app shell, and a rehearsal script runner used to capture the screens. When it starts, it starts the engine as a local process with the chosen model (Qwen3 1.7B, 4B or 8B), a free port and a token only it knows, waits for the engine's line saying it holds that port before it sends the token, and then talks to it over the loopback address (IR-04). Each model has its own memory folder, since notes belong to the model that wrote them. The application has two parts, Chat and Code (E-50); an earlier Swarm screen, which ran several agents with their own memories, was removed so that the app does two things well. Colour carries meaning only: memory is cyan, the model amber and the cloud yardstick grey (E-34, E-49). The screens below were captured from the running app with a real memory of 737 rooms; they illustrate the workflows, and the evidence that each requirement was met is in the test cases (Section {sec:testing}).

**Starting.** When the app starts, it draws the model's layers filling as their weights load (Figure {fig:app-load}); the memory panel above them shows how many rooms the memory holds. If the engine cannot start, the window says why and where it looked, instead of waiting without end.

![{#app-load} Starting the app: the model's 36 layers fill as their weights arrive ("loading 14/36"), before the first question](figures/app/loading-weights.png)

**Telling and asking.** In Chat, the user tells the model something with Remember and asks with Ask (Figure {fig:app-chat}). A remembered moment is judged by revision, filed on its shelf and read once by the model; a question is routed, its room is read, and the answer is written. Under each answer the app shows where it came from (memory, the model's own knowledge or the web), the time to the first word, and, from memory, the note read and whether it came from RAM or the SSD; under each remembered fact, the shelf it was kept on. A switch turns memory off, so the same question can be asked of the model alone, which then answers "I don't know" about the user's own facts.

![{#app-chat} Chat with memory on and off: a fact told earlier is answered from the room it was kept in ("room 609 · read from the SSD"); with memory off, the same question gets "I don't know"](figures/app/chat-memory-on-off.png)

**Shelves.** Moments told on "Auto" are filed by meaning (Figure {fig:app-shelves}), and each answer names the note and the shelf it read.

![{#app-shelves} Shelves in Chat (Qwen3 4B): moments told on "Auto" are filed on the Research and Personal shelves by meaning, and each answer names the note and shelf it read ("note 0 on Coding · read from the SSD")](figures/app/chat-shelves.png)

**General questions and reasoning.** A question that needs no memory is answered from the model's own knowledge; a thinking model's reasoning streams into a block that folds once the answer is written (Figures {fig:app-maths} and {fig:app-reasoning}), and what was learnt is kept on the Research shelf. Conversations are saved and listed, a new one can be started, and an answer can be stopped mid-way.

![{#app-maths} A general question answered by the 8B from its own knowledge, its reasoning folded ("Thought for 18.5 seconds"), labelled "from the model" and kept on the Research shelf](figures/app/chat-maths.png)

![{#app-reasoning} The 8B's reasoning, folded once the answer is written ("Thought for 27.8 seconds")](figures/app/chat-reasoning-folded.png)

**The weights view.** The tensors are drawn only while a model loads or when the user asks for them (Command-T), and can be shown large beside the chat (Figure {fig:app-weights}). While the model answers, the room it reads is marked and travels into the model, and each layer's row lights with how strongly that layer fired for each word: 32 measured numbers per layer per word, sent by the engine only while the app listens, so the benchmarks pay nothing for them (FR-19). With memory off, the memory stays dark and only the model's layers light (Figure {fig:app-onoff}).

![{#app-weights} The weights view, large beside the chat: the room an answer reads travels from the memory (rooms, top) into the model's 36 layers (bottom)](figures/app/weights-large.png)

![{#app-onoff} The weights view with memory on (left), where the room read lights and flows into the model, and off (right), where the model answers alone and the memory stays dark](figures/app/weights-on-off.png)

**Code.** Code is a coding agent on the same local model (Figure {fig:app-code}). The user picks a folder; the agent can list, search, read and edit files and run commands there, and every shell command waits for an explicit Allow. Its turns, tool calls and the files it opened or wrote are shown as it works, and with memory on what it learns about the project is kept on the Coding shelf for the next task (Figure {fig:app-cafe}). Building from memory needed small fixes to the agent, each with its test: the notes' answer rules no longer end a task; an empty workspace and the files still to write are named at every step; a look repeated with nothing changed is not run again; a reply cut off inside a tool call gets more room; a code step re-reads its eight closest moments (E-59); an answer that leaves the task's files unwritten is sent back once; and the attention record is worked out as each look is made, so a long desk no longer runs the graphics memory out (E-60).

![{#app-code} Code: the agent lists the files of a project folder, reads `money.py` and answers from what it read; the answer is kept in memory](figures/app/code-reads-then-answers.png)

![{#app-cafe} Code with the 8B: a one-page café website written as `index.html` and `style.css` in two tool calls, and kept in memory](figures/app/code-cafe-site.png)

### Memory for Other Runtimes: the Ollama Pairing

Ollama runs its own model and lets no outside code put keys and values into it, so the engine gives it memory as words. A proxy on 127.0.0.1:11435 speaks Ollama's own API; before a chat is forwarded to the real Ollama, the proxy recalls the closest notes on the last user message and puts them, at most 8 notes and 512 tokens, at the front of that message (E-33). After the answer has streamed back, the exchange is remembered on a background worker. The same code serves an OpenAI-compatible endpoint on 127.0.0.1:11436 in front of Ollama, LM Studio or mlx_lm.server (E-47). Through these doors memory goes in as words; the engine's notes need the engine.

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

### Test Strategy and Acceptance Criteria

The purpose of testing was to show whether the implemented system satisfies the requirements of Chapter 4. The scope was the engine, the assistant, the application, the pairing and the benchmark harness; the environment was the MacBook Pro of Table {tab:hardware}; the test data were the scripted lives, the Long Haul, the public suites and the multimodal files, none of them personal. A test passed only when its observed result met an expected result written beforehand: for the non-functional requirements, the thresholds of Table {tab:nfr}, written before the runs that tested them (E-19, E-40); for the functional requirements, the behaviour the requirement states. Testing was complete when every automated test passed, every requirement with a threshold had been measured, and every defect found had been fixed and retested or bounded and reported. Testing used five levels:

1. **Unit and integration tests.** White-box pytest tests in 49 files cover the rooms, notes, tiers, vault, core, reach, metrics, events, pairing, the app's routes and security, the Code agent, the assistant's router, research, revision and shelves, and every part of the benchmark harness (the Long Haul's generator and grader, the runners, the suites and the cost ledger). On 5 November, 788 tests passed and 5 were skipped.
2. **System tests.** The benchmark runs were judged against the non-functional requirements of Table {tab:nfr}, whose thresholds were written before the runs that tested them (E-19, E-40).
3. **Security tests.** Requests with a foreign host, a foreign origin, no token or a non-JSON body were sent to the engine's server and the proxies.
4. **Deployment test.** The installer and the health check were run, and the Mac app was built, installed in the Applications folder and run with the 1.7B, 4B and 8B models.
5. **Demonstration.** Chat and Code were used with a real memory, and the screens were captured from the running app (Section {sec:app-impl}). Black-box positive, negative and boundary cases were included: memory off, never-told questions, foreign requests, a second process, a cost cap, and a never-said name.

User acceptance testing and an accessibility audit were not done.

### Test Cases and Results

Table {tab:testcases} gives each test case with its requirement, its expected and actual result and its verdict.

Table: {#testcases} Test cases and results

| Test ID | Traceability | Scenario | Expected result | Actual result and evidence | Verdict |
|---|---|---|---|---|---|
| T-01 | All FR | The automated suite | Every test passes | 788 passed, 5 skipped (5 November) | Pass |
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
| T-15 | FR-18, FR-19 | The Mac app with Qwen3 4B and 8B | Chat and Code work with memory on and off; the weights view moves only with measured events | Figures {fig:app-load} to {fig:app-cafe} | Pass (demonstration) |
| T-16 | FR-20 | A fact told through the OpenAI-compatible endpoint, asked back through the real Ollama | The fact comes back | "Pilipili", with 187 characters of notes (E-47) | Pass |
| T-17 | FR-22 | The Long Haul built twice from seed 1, and extended | Identical scripts; the first 110 days unchanged by the extension | Generator tests pass; checked event for event (E-39) | Pass |
| T-18 | FR-27 | 14 routing questions on the 8B's Long Haul memory, including one never-said name | Questions about the user's records go to memory; others to the model | 13 of 14 routed right; the miss, the never-said name, was then answered honestly (E-55) | Pass |
| T-19 | FR-30 | Five test moments judged on the 4B: two updates, a repeat and two new facts | UPDATE, UPDATE, SAME, NEW, NEW | 5 of 5 as expected; the old notes kept and marked superseded (E-56) | Pass |
| T-20 | FR-31 | Twelve test sentences told on "Auto" | Each filed on its shelf | 12 of 12, including the 8 not close to any shelf's examples (E-51) | Pass |
| T-21 | FR-29 | A photographed receipt attached, then asked about later | Its total and an item answered from memory | KES 730.00 and the item, "from memory · note 549" (Figure {fig:app-receipt}) | Pass (demonstration) |
| T-22 | FR-28 | A web page whose text tries to close its markers or give orders | The page is read as data only | Angle brackets neutralised and links limited to http(s), by the research tests | Pass |
| T-23 | Users | User acceptance; accessibility audit | Agreed criteria with representative users | Not run | Not tested |

### Defects Found and Retests

The measurements and the demonstrations found nine defects in the system or in its measurement (Table {tab:defects}). Each was fixed or bounded, and the affected runs were repeated or reported both ways.

Table: {#defects} Defects found and retests

| ID | Defect and how it was found | Correction | Retest |
|---|---|---|---|
| D-01 | The 1.7B declined facts sitting on its desk at 1M and 2M; diagnosis ruled out retrieval and sleep and found the yardstick's wording (E-37) | The 1.7B is run with both wordings; the others keep the yardstick's, as planned | Both reported (Section {sec:wording}) |
| D-02 | The engine's process held 19.2 GB, not the 5.7 GB the records showed: MLX kept freed graphics buffers up to the whole limit and swap filled (E-40) | The buffer cache capped at 1 GB; every record now logs the process's footprint | 7.5 GB, identical answers (E-41) |
| D-03 | Ollama, bare, BABILong: 58 of 100 answers thrown out as "thinking" with no thinking in them (E-43) | An empty think block is cut off the answer; real thinking is still an error | The 58 resumed (Section {sec:ollama-suites}) |
| D-04 | Ollama, HARP: at the shared 400-token limit, 82 of the bare 1.7B's 120 answers and 95 of the paired one's were cut off mid-working (E-43) | The same room to work in words as Claude has to think (8,192 tokens); the 400-token records kept | Rerun (Section {sec:ollama-suites}) |
| D-05 | Ollama's `qwen3:4b` had become the Thinking build (E-33) | The 4B runs as `qwen3:4b-instruct-2507-q4_K_M` | Pass |
| D-06 | A crash between appending a moment's notes and saving the index would misplace later moments (E-27) | Opening a memory cuts each room file to its indexed length; a test covers it | Pass |
| D-07 | Routing blind, the 8B sent "the number plate of Kitengela Ventures' delivery truck" to its own knowledge (E-55) | The router sees the closest note; a question naming a person or business in the closest notes goes to memory | 13 of 14 (T-18) |
| D-08 | A photographed receipt was not recalled: 737 Long Haul notes outscored it on its own shelf (0.81 against 0.70) | The closest moment of every other shelf within 0.12 of the best is read too | Recalled (T-21) |
| D-09 | Switching models in the app marked the new engine failed ("exit 15"): the old process's exit handler ran late | The handler acts only for the process it was attached to | Pass: 1.7B, 4B and 8B switched in turn |

## Version Control and Implementation Evidence {#vc}

**Project repository:** https://github.com/Satasdin/CAMR (public). The repository holds the baseline at its root and the engine in `v2/`, with their full histories; the final engine, the Mac app, its records and this report are on the branch `camr-build`. It contains the README, the user guide and the decision log; the installer, the scripts and the tests; every benchmark record and the Claude cost ledger; the Mac app's Swift package; and the generator scripts of this report's diagrams and charts. `.gitignore` excludes the virtual environment, model weights, datasets and `work/`, where contenders' memories are rebuilt on every run; no key, token or personal memory is committed, and the yardstick's key is read at run time from a private file outside the repository. The branch-based workflow kept the engine's development apart from the baseline: each increment of Section {sec:dev-approach} was committed as it was measured, and each benchmark job committed its records as it finished, so the history shows when each number was made and by which code. GitHub Actions runs the tests that need no MLX on every push (NFR-16).

## Author Oversight and Use of AI-Assisted Tools {#ai-use}

Claude (Anthropic), used through Claude Code, assisted with this project. Under the student's direction it wrote and revised the engine, the app, the harness and their tests; ran the experiments; and drafted the documentation, including the decision log, the user guide and drafts of this report. The student set the problem, the objectives, the scope and the direction of the work, and made the calls recorded as the student's own, such as making the engine the project (E-29), pushing the Long Haul past 2 million tokens (E-39), asking for the RAM to be optimised (E-40) and removing Swarm from the app (E-50). The output was checked by running the automated tests, by the records, which name the machine and the code behind every number, and by reading the outputs themselves. Requirements were written before the runs that tested them, and the requirements that were not met are reported as measured. Claude also served, separately, as the yardstick in the benchmarks; that role is unrelated to its role as a tool. The student made the final decisions and takes full responsibility for the work. The tool was Claude Code with Claude Opus models (Opus 5.5 in the final weeks). [[Student to confirm this statement and the model versions.]]

## Evaluation Results {#eval}

> **In plain words.** A 4B model with CAMR answers a long project's questions about as well as Claude Sonnet alone at 2 million tokens, and better past Claude's window, at a fraction of the wait and in a process of 5 to 8 GB. It stays as fast as memory grows. It is weakest at joining facts and at following a design over weeks.

This section presents the measured results experiment by experiment, each with its conditions, its baseline and its interpretation. Section {sec:discussion} then discusses them by objective.

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

The wait for the first word is the sum of the steps an answer takes before it writes (Equation {eq:latency}); every record logs each term, so a slow answer can be traced to its step.

$$t_{\text{first}} = t_{\text{choose}} + t_{\text{core}} + t_{\text{fetch}} + t_{\text{wake}} + t_{\text{desk}} + t_{\text{prefill}} + t_{\text{token}}$$ {#latency} [Time to the first word]

The first five terms are the retrieval time of Table {tab:metrics} (choosing the room, building the core, reading the room, waking it when asleep, laying the desk); \(t_{\text{prefill}}\) is reading the closest moments, the date and the question as words, and \(t_{\text{token}}\) is writing the first token. When a room is read from the SSD, its read bandwidth is the bytes read over the fetch time (Equation {eq:bandwidth}).

$$\text{bandwidth} = \frac{\text{read bytes}}{t_{\text{fetch}}}$$ {#bandwidth} [Read bandwidth of a room fetched from the SSD]

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

### Storage at 8 and 4 Bits {#bits-results}

The 1.7B with CAMR was rerun on the Long Haul's first two cuts with its rooms stored at 16, 8 and 4 bits (records of 5 November, `v2/records/bench/2026-11-05/`; Table {tab:bits}). At 8 bits it answered as at 16 bits, 14 and 20, with the room files held to 8.6 GB at 256K by an 8 GB disk budget against 34.3 GB at 16 bits; at 4 bits it lost 2 answers at 256K (18 against 20) and took 9.7 GB.

Table: {#bits} Room storage at 16, 8 and 4 bits (`engine:qwen3-1.7b`, the first two cuts)

| Rooms stored at | Right, 64K (34) | Right, 256K (40) | Disk at 256K | First word p50, 256K | Process RAM, 256K |
|---|---|---|---|---|---|
| 16 bits | 14 | 20 | 34.3 GB | 0.10 s | 5.2 GB |
| 8 bits (8 GB disk budget) | 14 | 20 | 8.6 GB | 0.13 s | 3.8 GB |
| 4 bits | 14 | 18 | 9.7 GB | 0.15 s | 4.1 GB |

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

### Multimodal Memory {#media-results}

The engine can also remember files (E-44). A PDF becomes one moment per page, an image its caption and the text written in it, and a video a frame every 2 s, each described with its time, by a vision model that turns the file into words once; the moments are then kept like any others, with the file copied into the vault. The multimodal benchmark tells 21 files of Mama Njeri's Kitchen (PDF invoices and menus, photographed receipts and notices, charts and short whiteboard videos) among about 100,000 tokens of the Long Haul's own events, all in the first 60,000 tokens, and then asks 37 questions graded by the Long Haul's rules: 29 about facts planted in the files, by kind of file, and 8 never-said questions where declining is right. The contenders are Qwen2.5-VL-3B with CAMR, alone with its newest 32K tokens, and with the file itself in the prompt as an upper bound; Qwen3 4B with CAMR and alone, reading the vision model's words; and Ollama's `qwen2.5vl:3b`, paired and bare.

Table {tab:media} gives the results (VL-3B is Qwen2.5-VL-3B; 4B is Qwen3 4B; Gemma 3 is Ollama's `gemma3:4b`) for seed 1 by kind of file, with each contender's total on a second draw of files and questions (seed 2), from the records `*-media-*.json` of 4 November.

Table: {#media} Multimodal memory: right answers by kind of file (seed 1: 29 planted facts and 8 never-said questions; seed 2: the same counts)

| Contender | PDF (8) | Image (9) | Chart (6) | Video (6) | Never (8) | Seed 1 (37) | Seed 2 (37) | First word | RAM |
|---|---|---|---|---|---|---|---|---|---|
| **4B + CAMR (VL-3B's words)** | **8** | **9** | **6** | **6** | **8** | **37** | **35** | 0.34 s | 7.3 GB |
| 4B alone (newest 64K) | 1 | 5 | 3 | 1 | 7 | 17 | 18 | 0.32 s | 12.4 GB |
| VL-3B + CAMR | 8 | 9 | 6 | 6 | 4 | 33 | 31 | 0.21 s | 5.1 GB |
| VL-3B + CAMR, looking again | 8 | 9 | 6 | 6 | 3 | 32 | | 0.80 s | 8.7 GB |
| VL-3B, file in the prompt | 8 | 9 | 6 | 6 | 5 | 34 | 33 | 1.23 s | 4.4 GB |
| VL-3B alone (newest 32K) | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0.14 s | 6.3 GB |
| Ollama VL-3B + pairing | 8 | 9 | 6 | 6 | 5 | 34 | 33 | 0.22 s | 1.9 GB† |
| Ollama VL-3B alone | 0 | 0 | 0 | 0 | 5 | 5 | 2 | | 1.9 GB† |
| Ollama Gemma 3 + pairing | 8 | 7 | 6 | 5 | 2 | 28 | | 0.36 s | 1.9 GB† |
| Ollama Gemma 3 alone | 0 | 0 | 0 | 1 | 4 | 5 | | | 1.9 GB† |
| 4B + CAMR (Gemma's words) | | | | | | 36 | | | |

With CAMR, every planted fact from every kind of file was recalled on seed 1, at least 40,000 tokens after the file was told, by the vision model and by the text-only 4B: 29 of 29 each, and 27 to 28 of 29 on seed 2. The 4B with CAMR answered all 37 on seed 1 and 35 on seed 2, declining every never-said question, and beat the vision model holding the file in its prompt (34 and 33) at under a third of its wait. The models alone recalled almost nothing: by the questions, the files had left their windows. Ollama's vision model, given memory as words through the pairing, did as well as the engine's vision model (34 and 33), in the smallest process. A second vision model, Ollama's Gemma 3 4B, described the files itself and, through the pairing, recalled 26 of the 29 facts against 1 alone, but invented answers to 6 of the 8 never-said questions. Given Gemma's descriptions instead of Qwen2.5-VL's, the 4B with CAMR answered 36 of 37: the memory, not the describer, carried the answers. Figure {fig:media} sets the totals side by side. Looking at the image again added nothing on this set and cost nearly four times the wait. The vision models' weakness was honesty, not recall: with memory they invented answers to 3 to 5 of the 8 never-said questions, where the 4B invented none. († Ollama's own peak resident memory, not a process footprint.)

![{#media} Multimodal memory: right answers of 37 on two draws of files, with CAMR (cyan), with the file in the prompt (grey) and alone (amber)](figures/ch5/media.png){width=15.9}

### Code: Café Websites from Memory {#code-results}

The Code agent was benchmarked on building from what it was told (E-58). Memory is told six notes about a café: its name, two brand colours as hex, three menu items with prices in KES, its opening hours, its address, and the rule that prices always show KES and two decimals. The agent is then asked, in an empty workspace, for "a one-page website for our café: index.html and style.css". Ten rules grade each site with no model: both files exist, the HTML parses, it links `style.css`, and it holds the name, all three items, every price as "KES n.00", the opening and closing times, the address and both colours, with nothing invented (no price or menu word the notes do not hold). Shell commands are refused, since a site needs only file writes. Each model ran four ways on five cafés: memory off, the notes pasted into the prompt (the ceiling), memory with the notes on the Coding shelf the day before, and note context, with the notes told ten days earlier among 6,000 tokens of Long Haul events (Table {tab:cafe}).

Table: {#cafe} Code: café websites, average rules met per site (of 10) over five cafés (records `013817-code-cafe-code-qwen3-4b.json` and `014735-code-cafe-code-qwen3-8b.json`)

| Model | Memory off | Notes in the prompt (ceiling) | Memory on | Notes told 10 days earlier among noise |
|---|---|---|---|---|
| Qwen3 4B | 3.0 | 9.8 | **10.0** (5 of 5 complete) | 9.2 |
| Qwen3 8B | 4.0 | 10.0 | 9.6 | 9.2 |

With memory, the sites were as good as with the notes in the prompt. The 4B met every rule on every café from memory (10.0 against 9.8), in fewer steps (3.6 against 9.0) and about half the time (18.0 s against 36.0 s per site); the 8B met 9.6 against 10.0. With memory off the page worked but knew nothing: the 4B invented a menu every time (cappuccino, espresso, latte) and failed "nothing invented", while the 8B wrote a two-line welcome page with no menu. Told ten days back among other events, memory still found most of it, 9.2 on both models. The records show three kinds of miss: the price rule (three runs), whose note was on the desk though the model still wrote "KES 220"; one café's colours and address, which were in neither the room memory chose nor its closest words; and, for the 8B with memory on, one site with no stylesheet, after the model twice said it would write `style.css` and stopped.

### The Assistant and the Shelves in the App {#assistant-results}

On twelve test sentences, "Auto" filed all 12 on the right shelf, including all 8 that were not close to any shelf's examples (E-51). In the app, three moments told on "Auto" went to the Coding, Research and Personal shelves, and each later answer read the right shelf, with its first word in 111 to 119 ms. The warm-up's kernels alone took 24 ms off the 4B's first answer, from 111 to 87 ms; a room not read ahead still came off the SSD in milliseconds, the first Long Haul question reading 68 MB in 8 ms (E-52).

The assistant's parts were checked in the app on the night of 4 November (E-55 to E-57). The router adds about 0.1 s to a question. Reading the closest moment of every other shelf when it is within 0.12 of the best found a photographed receipt that the 737 Long Haul notes had outscored (closeness 0.70 against 0.81). Revision judged five test moments on the 4B correctly, 5 of 5: a raised minimum order and new opening hours as updates, a repeat as the same, and a birthday and another branch's hours as new. The eyes read a photographed receipt line by line (a total of KES 730.00, paid by M-Pesa) in about 25 s including loading the vision model, and the 8B then answered both questions about it from memory. When the router sees memory, a question naming a person or business found in its five closest notes goes to memory outright, and otherwise the model judges with the closest note in view; routing blind, the 8B had sent "the number plate of Kitengela Ventures' delivery truck" to its own knowledge, and seeing memory it routed 13 of 14 test questions right on its Long Haul memory, the miss being a never-said name that it then answered honestly (E-55). Figure {fig:app-receipt} shows the receipt answered later from memory. These are demonstrations on a handful of cases, not benchmarks.

![{#app-receipt} A photographed receipt read into memory by Qwen3-VL-4B-Thinking, its total and an item answered later by the 8B from memory ("from memory · note 549 · read from the SSD")](figures/app/chat-receipt-photo-recalled.png){width=15.9}

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

## Discussion and Limitations {#discussion}

This section discusses the results by objective. For each objective it states the implemented output, the evidence, the acceptance criterion, the observed result and what the result permits the study to conclude, compares it with the baseline and with Chapter 2 where that helps, and analyses the failures. The limitations close the chapter.

### Results by Objective {#glance}

Table {tab:scorecard} gives each claim of the study a verdict, grouped by the objective it serves, with the section that supports it.

Table: {#scorecard} Scorecard: each claim, its evidence and whether it was met

| Objective | Claim | Evidence | Result | Verdict |
|---|---|---|---|---|
| i | Selective techniques help a small model; separately written notes do not combine | Baseline; rooms build (Sections {sec:baseline-results}, {sec:rooms-results}) | Bridging 35.8% → 78.4% full-support recall; separate notes 2 of 46 facts against 32 as words | Met |
| ii | Notes and words know the same within a room | Rooms build (Section {sec:rooms-results}) | 164 against 163 facts | Met |
| ii | Files remembered: PDFs, images, charts, video | Multimodal memory (Section {sec:media-results}) | 29 of 29 planted facts with CAMR, for the vision model and the 4B; 0 for the vision model alone | Met, on a small test |
| iii | Lighter than the model reading its own window | Footprint (Section {sec:ram-results}) | 5.4–7.5 GB against 15.2 GB (4B); 8.1–8.8 GB against 13.6 GB (8B) | Met, after the cap (D-02) |
| iii | No slower as memory grows | Speed as memory grows (Section {sec:speed-results}) | First word 0.11 → 0.08 s and RAM 4.26 → 4.23 GB from 112K to 2.01M tokens | Met |
| iii | Notes are at least 10 times sooner than words | Speed bench (Section {sec:rooms-results}) | 4.6 times at 2,000 words | Not met |
| iv | A small model with CAMR answers like a cloud model on a long history | Long Haul at 2M (Section {sec:haul-results}) | 4B + CAMR 29 of 73; Sonnet alone 32, Opus 31, Haiku 10 | Nearly met at 2M |
| iv | Past the cloud model's window, memory wins | Long Haul at 3M and 4M (Section {sec:past-window}) | 4B + CAMR 29 and 29; Sonnet 13 and 10; Haiku 10 and 10 | Met |
| iv | Memory beats the same model without it | Long Haul, every cut | 4B: 25/26/25/29 against 18/14/20/11; 8B: 26/26/24/27 against 15/11/15/11 | Met |
| iv | As accurate as conventional RAG, and faster | Section {sec:disc-rag} | 164 against 166 facts (RAG baseline); first word 0.07 against 0.15 s; Long Haul 0.10–0.14 against 0.38–0.40 s through RAG | Met on speed; level on accuracy |
| iv | Faster than the cloud | First word (Section {sec:yardstick}) | 0.2–0.3 s against 13–105 s for Sonnet and Opus | Met |
| iv | Honest about what was never said | Never-said family | 4B declined 9 of 10 at 2M and 10 of 10 past it; Claude 10 of 10 | Met for the 4B; not for the 1.7B with its own wording |
| iv | Memory recovers knowledge, not reasoning | Families at 2M (Section {sec:families}) | Facts 6 of 10 (Sonnet and Opus 4, Haiku 0); two hops 0; the growing page 0 for everyone | Met as predicted |
| iv | Code built from memory | Café websites (Section {sec:code-results}) | 4B: 10.0 of 10 rules with memory, 9.8 with the notes in the prompt, 3.0 with memory off | Met, on five cafés |
| v | The best reach | Reach (Section {sec:reach-results}) | Project 26 of 40; global 24; session 11 | Project reach |
| v | Smaller rooms, same answers | Storage at 8 and 4 bits (Section {sec:bits-results}) | 8 bits: 14 and 20, as 16 bits; 4 bits: 14 and 18 | Met at 8 bits |

### Objective i: Memory Techniques and Their Limits on the Device {#disc-obj1}

**Implemented output and criterion.** The techniques reviewed in Chapter 2 were built as switchable choices so that their value on a small on-device model could be measured, not assumed: similarity ranking against the composite of recency and importance, a gate and entity bridging in the baseline; and, in the engine, saved keys and values written one moment at a time against rooms written as one page. The criterion was a controlled comparison for each choice on held-out questions.

**Observed result.** Selective techniques that keep what the model reads small helped a small model; techniques that gave it more, or less related, text did not. Bridging found the second hop without a graph, raising full-support recall on 2WikiMultiHopQA from 35.8% to 78.4% at the same budget, while weighting by recency and importance lowered it (Section {sec:baseline-results}). Reusing a model's own keys and values worked within one room, where notes and words knew 164 and 163 facts, but notes written separately and laid side by side did not combine for a small reader (2 of 46 facts against 32 from the words; Section {sec:rooms-results}). This is the limit that cache blending works around by re-computing part of each stored cache where caches meet (Yao et al., 2025), and the reason the engine reads one room per question. A long window was not a substitute for memory: Claude's one-million-token window held only the newest days of a 3 or 4 million-token history and recalled nothing planted earlier (Section {sec:past-window}), which agrees with the evidence that long contexts are used unevenly even when they fit (Liu et al., 2024).

**What this permits.** On the tested device and models, the applicable techniques are those that keep the desk small and related; saved caches are usable only as whole rooms; and a long context window cannot stand in for a memory that outgrows it.

### Objective ii: The Design of the Engine {#disc-obj2}

**Implemented output and criterion.** The design of Chapter 4 was implemented: a write path that keeps each moment as the model's notes in a room, a read path that lays one room and four closest moments on the desk, tiers and sleep under fixed budgets, a vault, reach, and the assistant around them. Its acceptance criterion was NFR-07: within one room, notes must know at least 95% as many facts as the same desk read as words, with at most 3 extra false memories of 45; the assistant's parts were judged against the behaviour their requirements state.

**Observed result.** NFR-07 was met: 164 against 163 facts and 25 against 24 false memories, with the same answer on 3,483 of 3,600 questions (T-08; Section {sec:rooms-results}). On errands, where a tool needs the exact fact, the rooms build did three times as many right as the baseline (122 against 40), because it opens the closest room however a task is worded. The assistant behaved as specified on its test cases: 13 of 14 questions routed right, five revisions judged as expected, and 12 of 12 moments filed on the right shelf (T-18 to T-20), and every fact planted in PDFs, photographs, charts and videos was recalled from memory (Section {sec:media-results}). The design's structural limit showed in the families: a question sees one room, so facts told in two places were almost never joined (0 of 10 two-hop questions at 2M for the 4B; Section {sec:families}). Systems that page text in and out of a model's context (Packer et al., 2023) face the same choice of what to bring in; CAMR brings in one room already read.

**What this permits.** The design keeps and finds memory faithfully within a room and serves chat, files, code and evaluation through one read path. It does not join facts across rooms, and the assistant's results are demonstrations on a handful of cases, not benchmarks.

### Objective iii: The Engine on a Consumer Laptop {#disc-obj3}

**Implemented output and criterion.** The engine and the Mac app ran on a MacBook Pro M5 Pro with 24 GB and no dedicated graphics card, with the models and the memory on the Mac. The criteria were NFR-01 to NFR-06: a first word under 0.5 s at 2,000 words; notes at least 10 times sooner than words; no climb in the first word or RAM as memory grows; disk and RAM within budget; a capped buffer cache; and retrieval within 10% of the answer's time.

**Observed result.** Five of the six were met and one was not (Table {tab:testcases}). The first word at 2,000 words came in 0.233 s (NFR-01). From 112 thousand to 2.01 million tokens of history, the 1.7B's first word stayed at 0.08 to 0.15 s, retrieval at 17 to 24 ms and RAM at about 4.3 GB, while sleep held the room files at their 40 GB budget (NFR-03, NFR-04; Section {sec:speed-results}). Retrieval took 4% of the 4B's answer time (NFR-06), where the baseline's 0.5B reader had spent 56% under contention. After the buffer cache was capped, the 4B's whole process needed 5.4 to 7.5 GB at 3 and 4 million tokens, against 15.2 GB for the same model reading only its newest 64,000 tokens (NFR-05; Section {sec:ram-results}). Notes were 4.6 times sooner than words, not 10 times (NFR-02): the mark had been estimated on the slower MacBook Air, and notes still pay for the SSD read and the copy into graphics memory. The cost of memory moved to storage: the room files reached their budget by about 1 million tokens, and past it most rooms were asleep and read as words (Table {tab:tiers}). Storing rooms at 8 bits, about half the size of 16 bits, gave the same answers, and with an 8 GB disk budget held the room files to 8.6 GB at 256K tokens against 34.3 GB (Section {sec:bits-results}).

**What this permits.** A memory that grows to millions of tokens can run beside a small model on one Mac without slowing it or making it heavier, within a disk budget. The claim holds for the Mac and models tested; 8 GB Macs and older chips were not measured.

### Objective iv: The Capability Gap by Task Type {#disc-obj4}

**Implemented output and criterion.** The engine was evaluated against the same models without memory and against Claude Haiku, Sonnet and Opus 5.5 reading as much of the history as their windows hold, on the same questions graded by the same rules, with the first word, the RAM and the cost of every answer. The criterion was a comparison by family, with knowledge-bound and reasoning-bound families reported apart.

**Observed result.** Within its window the cloud model was better; beyond it, memory was. Up to 1M tokens Sonnet answered 28 to 43 questions per checkpoint against 25 to 26 for the 4B with CAMR; at 2M the 4B with CAMR answered 29 of 73 against Sonnet's 32 and Opus's 31; at 3M and 4M it answered 29 both times while Sonnet fell to 13 and 10 (Sections {sec:haul-results} and {sec:past-window}). Against the same model without memory the gain was large past the window: 29 against 11 for the 4B and 27 against 11 for the 8B at 2M. The first word came in 0.2 to 0.3 s, against 13 to 105 s for Sonnet and Opus (Section {sec:yardstick}). By family, memory closed the knowledge gap but not the reasoning gap: CAMR led on facts told far back (6 against 4 of 10) and on code that had to use the project's own helpers (4 against 2), and trailed where several moments must be weighed (changed facts, look-alikes, corrected mathematics); no model built the page that needed a design from week 1 and a change from day 61 (Section {sec:families}). The baseline had found the same on public benchmarks: with memory, 20 of 22 small models matched the cloud model on long-tail facts, while memory left an 83-point gap on arithmetic (Section {sec:baseline-results}), in line with the finding that retrieval helps most on less popular facts (Mallen et al., 2023). The same held beyond plain text. Building café websites from memory, the 4B met 10.0 of 10 rules against 9.8 with the notes pasted in and 3.0 with memory off (Section {sec:code-results}); told 21 files among 100,000 tokens, the 4B with CAMR answered 37 of 37 against 17 alone (Section {sec:media-results}). The 4B was also honest: it declined 9 of 10 never-said questions at 2M and all 10 beyond it. Memory as words through the Ollama pairing was mixed: it helped where a worked example carried to a new problem (HARP, 34 against 28) and hurt where the answer is the newest of many similar mentions (BABILong, 20 against 39; Section {sec:ollama-suites}).

**What this permits.** On one scripted project, a 4B model with CAMR nearly closes the gap to a cloud model at 2 million tokens and exceeds it past the cloud model's window, at a fraction of the wait and in a process of 5 to 8 GB; it closes knowledge-bound gaps, not reasoning-bound ones. The differences of one to three answers are within the noise of 10 questions per family.

### Objective v: How Much to Read, and What Each Part Contributes {#disc-obj5}

**Implemented output and criterion.** Controlled comparisons varied one choice at a time: the desk, the room size, notes against words, the reader's size, the wording, the reach, the precision of stored rooms and the buffer-cache cap. The criterion was the change in right answers, time and resources against the same set-up with that one choice reverted.

**Observed result.** For a small reader the best desk was small and fixed: one room of at most 512 tokens plus four moments re-read knew 158 facts on the development lives, more than three rooms read as words (144) or either part alone, and larger rooms knew fewer facts at every setting tried (Section {sec:rooms-results}). Saving notes rather than words bought speed, not accuracy: the same 1.7B answered 14 to 20 with notes and 16 to 17 with the same memory as words, three times sooner, at 40 GB of disk against 0.1 GB (Section {sec:notes-words}), a comparison that is clean only at 64K and 256K, since most rooms were asleep later. A larger reader did not raise the ceiling: the 8B and the 27B answered 27 at 2M against the 4B's 29 (Section {sec:bigger}), so the memory, not the reader, set it. The smallest model's wording mattered more than its memory: its own wording raised its score from 15 to 21 at 2M but cut its honest declines from 7 to 3 (Section {sec:wording}). Project memory was the best reach (26 of 40 against 11 for session and 24 for global; Section {sec:reach-results}). Rooms at 8 bits kept every answer and 4 bits lost two (Section {sec:bits-results}), and the buffer-cache cap halved the process's RAM with identical answers (Section {sec:ram-results}).

**What this permits.** The engine should read a small, fixed desk per question, keep one memory per project, store rooms at 8 bits and cap the buffer cache; the saved notes are justified by speed, and a 4B reader is the best trade of answers against time and RAM on this Mac.

### CAMR Against Conventional RAG and Long-Context Pipelines {#disc-rag}

The study's central comparison is between CAMR's memory, in which the model reads one room of its own saved notes already read plus four moments as words, and the conventional pipelines it is meant to replace: retrieval-augmented generation (RAG), which retrieves the closest text chunks and pastes them into the prompt to be read again at every question (Lewis et al., 2020), and long context, which pastes as much of the history as the window holds. Several experiments already measured these pipelines on the same questions, and Table {tab:ragcompare} brings them together. The baseline, CAMR v1, is itself a conventional RAG pipeline with similarity ranking, a gate, entity bridging and a token budget; the Ollama pairing is RAG over CAMR's own memory, with the closest notes, at most 8 and 512 tokens, put before the last message; and the "words" contenders read CAMR's rooms as plain text.

Table: {#ragcompare} CAMR's memory against conventional pipelines, from the experiments of Section {sec:eval}

| Comparison | CAMR's memory | Conventional pipeline | Section |
|---|---|---|---|
| Rooms build against the RAG baseline, proof lives, 1.7B, week 12 | 164 facts of 255; 25 false memories; first word 0.07 s; 1.82 GB | CAMR v1 (RAG): 166 facts; 29 false memories; 0.15 s; 2.24 GB | {sec:rooms-results} |
| Errands, where a tool needs the exact fact | 122 of 255 right | CAMR v1 (RAG): 40 | {sec:rooms-results} |
| Long context: every note pasted in | 164 facts; first word flat at 0.07 s | 90 facts; first word 1.90 s and climbing | {sec:rooms-results} |
| The same room as notes or as words, 2,000 words on the desk | First word 0.233 s | 1.080 s (4.6 times slower) | {sec:rooms-results} |
| Long Haul, 1.7B, same wording: notes against RAG through the pairing | 14, 20, 17, 15 right; first word 0.10–0.14 s; 40 GB of disk | 16, 17, 16, 16 right; 0.38–0.40 s; 0.1 GB | {sec:notes-words} |
| Long Haul at 2M: the 4B with notes against a 27B reading the same rooms as words | 29 of 73; first word 0.21–0.31 s; 7.5 GB | 27 of 73; 2.2–2.4 s; 16–17 GB | {sec:bigger} |
| Long context in the cloud at 3M and 4M | 4B + CAMR: 29 and 29; under 0.4 s | Claude Sonnet alone: 13 and 10; 13–70 s | {sec:past-window} |
| Files: 37 questions, seed 1 | 4B + CAMR: 37; VL-3B + CAMR: 33 | Ollama VL-3B with RAG: 34; the file in the prompt: 34 | {sec:media-results} |
| Café websites, rules met of 10 (4B) | 10.0, in 3.6 steps | The notes pasted in the prompt: 9.8, in 9.0 steps | {sec:code-results} |

Three findings follow. First, on accuracy CAMR's memory matched conventional RAG rather than beating it: on the same questions the two were within one or two answers (164 against 166 facts; 14 to 20 against 16 to 17 on the Long Haul), which is within the noise of the samples. Its advantage on errands came from opening the closest room however a request was worded, where the RAG baseline's gate, tuned for questions, let requests fall past it. Second, on time and RAM CAMR was consistently better: the model does not re-read retrieved text, so the first word came two to four times sooner than RAG at the same size of reader, and about ten times sooner than a 27B reader given the same memory as words, in a process less than half the size. Long context was worst on both counts once the history grew: pasting every note in knew fewer facts and slowed with every week, and the cloud model's window forgot the start of the history. Third, the price of CAMR's memory is storage: saved notes take thousands of times the disk of their text, so past about 1M tokens most rooms slept and were read as words, which is RAG over well-organised rooms. CAMR is therefore best described as a RAG pipeline whose unit is a dated room of related moments that the model has already read, which keeps the speed of reading nothing twice where the disk allows and falls back to retrieval as words where it does not. Where the answer is the newest of many similar mentions, both RAG and CAMR need more than the closest few notes (BABILong: RAG 20 of 100 against 39 for the model's own window; Section {sec:ollama-suites}).

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
| Vision models invent answers about what was never told | With memory, 3 to 5 of 8 never-said questions answered (Table {tab:media}) | The describing model guesses where the 4B declines | Bounded: the 4B answers from the vision model's words |
| A rule in the notes is not always followed | The café price rule missed in three Code runs with its note on the desk (Section {sec:code-results}) | A small reader writes the common format | Open |
| Swarm was not measured | No benchmark | Built late, then removed from the app (E-50) | Removed |

### Limitations, Delimitations and Threats to Validity {#limitations}

Limitations are weaknesses of the evidence; each is stated with its likely effect.

1. **A scripted test.** The Long Haul is one invented project, fixed by its seed and built to be hard in known ways. It is not a sample of real work, and its results compare memories fairly on such a history but do not show how CAMR would serve a real user.
2. **Small samples.** Each checkpoint asks 34 to 73 questions, 10 per family (3 for the page), so a difference of one or two answers is within noise; the 3-answer gap at 2M between CAMR and Sonnet is not a reliable ranking. No run was repeated for variance; only the 4B's 3M checkpoint was run twice, with identical verdicts.
3. **Claude is a yardstick, not an opponent.** Claude answered with no memory, reading the newest part of the history that fits its window. A cloud model with its own memory would do better past its window; the comparison shows what a window alone does, not the best a cloud service could do.
4. **RAM before the cap is understated.** The 1.7B's and the 4B's RAM figures up to 2M were measured as MLX's peak, before the buffer-cache cap; the process held more (E-40). Their scores are unaffected.
5. **One machine.** Every Long Haul, suite and speed number was measured on one MacBook Pro M5 Pro with 24 GB (the desk design on the MacBook Air, and the baseline on CPU-only machines); answers also differ slightly between chips (158 facts on the Air and 164 on the Pro for the same design; E-17).
6. **Grading by rule.** A rule can miss a right answer worded in an unexpected way. Every raw answer is kept in the records, so any verdict can be checked by hand, but no hand audit was done for this report.
7. **What was not measured.** The engine's own contenders were not run on the public suites (E-36); LongMemEval and two further suites have loaders but no runs; the Code agent was measured only on five café websites per model; no user study and no accessibility audit were done; the app's screenshots come from one session.

Delimitations are boundaries chosen for the study: Apple-silicon Macs only; English text; frozen, quantised open models; no fine-tuning; memory on the device, with the cloud only as a yardstick. Threats to validity: internally, every contender read the same instructions and the same questions, and the one wording change (the 1.7B's) is reported both ways; externally, the results hold for one scripted project, one Mac and the models named.
