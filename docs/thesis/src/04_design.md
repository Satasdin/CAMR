# System Analysis and Design {#design}

## Introduction {#design-intro}

This chapter presents the analysis and design of CAMR (Capability-Adaptive Memory Retrieval): what the system must do, the quality conditions it must satisfy, the data and interfaces it depends on, and the diagrams that communicate its structure and behaviour. Chapter 3 adopted design science research with controlled experimentation (Hevner et al., 2004; Peffers et al., 2007) and an incremental development approach in which the measurement apparatus is built before the artefact it measures. CAMR is an AI artefact judged by experiment rather than a transactional information system, so the chapter uses a justified hybrid of views. Ten diagrams are used, each because the project needs that view. Structured analysis (Gane–Sarson) gives the system boundary: the context diagram. Object-oriented analysis and design (UML 2.5), the paradigm that suits an artefact built as separable components refined in increments, gives the actors and services (use case diagram, with use case descriptions as a table), the evaluation workflow (activity diagram), the parts and their classes (component and class diagrams), the handling of one question (sequence diagram), the life cycle of memory (state machine diagram) and the hardware (deployment diagram). The baseline's relational store is shown by its logical schema, and the engine, which has no transactional database, by its file and data design. All diagrams are drawn from generator scripts kept with this report, so they can be redrawn and checked against the code.

CAMR was built in three stages (Table {tab:stages}). The baseline, CAMR v1, stores short text notes in one SQLite file beside a frozen model. The engine's first build (the rooms build) replaced text with the model's own keys and values, saved in rooms on the SSD. The final engine added a core that stays in RAM, tiers that move rooms between RAM and the SSD and put them to sleep, a vault of linked plain-text notes, reach, per-answer metrics, an assistant around the memory and a pairing with Ollama. This chapter designs the final engine and keeps the baseline's design where the evaluation still uses it. Decisions from the project's decision log are cited as E-nn (Appendix B); the implementation, the application's screens and every measured result are reported in Chapter 5.

Section {sec:requirements} states and traces the requirements. Section {sec:analysis-diagrams} presents the analysis diagrams and Section {sec:design-diagrams} the design diagrams. Section {sec:changes} justifies the changes from the proposal, and Section {sec:design-summary} summarises the chapter.

Table: {#stages} The three stages of CAMR

| Aspect | CAMR v1: the baseline | The rooms build | CAMR: the final engine |
|---|---|---|---|
| A memory is | A text note with embedding, importance, timestamps and source | A dated moment: its words, its embedding and the reader's keys and values at every layer | The same moment, also kept as a linked Markdown note in a vault |
| Store | One SQLite file with sqlite-vec | One append-only file per room on the SSD, a JSON index, a NumPy vector file | The same, plus tiers (RAM, SSD, asleep), a vault and one folder per reach or shelf |
| Read path | k nearest notes, gate, entity bridging, token budget | One room as notes, plus the four closest moments as words | The same desk after a core of standing facts; the room comes from RAM, the SSD or, when asleep, as words |
| Frozen reader | 0.5B–3B models through Ollama | Qwen3-1.7B through MLX | Qwen3 1.7B, 4B or 8B through MLX; larger models and Ollama read the memory as words |
| Embedder | bge-small-en-v1.5 | Qwen3-Embedding-0.6B | Qwen3-Embedding-0.6B |
| Cloud model | Kimi K3: ceiling and escalation | None | Claude Haiku, Sonnet and Opus 5.5, as a yardstick only |
| Interfaces | CLI, web app, inspector | One local web page | A native Mac chat app (CAMR, RAG or no memory, and Compare), the Ollama pairing, an OpenAI-compatible endpoint, a Python library |

## System Requirements {#requirements}

The system requirements identified for this project are presented in the following subsections. They were derived by working backwards from the objectives (Section {sec:specific-objectives}) and the measurements the evaluation needs (Section {sec:measurement}), then revised as the three stages were built. Following ISO/IEC/IEEE 29148:2018, each requirement has a unique identifier, states one thing, and names its priority, source and verification method.

- **Priority:** MoSCoW (Must, Should, Could).
- **Source:** the objective (i–v) it serves; the stage it applies to (v1 for the baseline, E for the engine); and where the requirement or its threshold is recorded: the proposal (P §), the decision log (E-nn), the baseline's findings log (Fnn) or the code.
- **Verification:** inspection (I), demonstration (D), automated test (T) or measurement (M).

No threshold was invented. Every number comes from the proposal, a design constant in the code, or a pass mark written in the decision log before the run that tested it (E-19); otherwise the requirement is a comparison or a behaviour that can be shown. The stakeholders are the user, who needs private, offline and honest answers; the researcher, who needs reproducible measurements; and the supervisor and examiners, who need traceable evidence.

### Functional Requirements

Functional requirements describe what the system must do. They fall into six groups, listed in full in Table {tab:fr}:

- **The baseline's paths (FR-01 to FR-06).** Documents become screened, embedded notes; a question's nearest notes are ranked, gated, bridged and packed into the model's prompt.
- **Keeping memory (FR-07 to FR-11).** A moment is read once by the frozen model, placed in a room and appended to the room's file; it is also written to the vault; rooms move between tiers under budgets.
- **Answering (FR-12 to FR-17).** A question's room and closest moments are laid on the desk after the core, within the reaches the session reads; memory can be switched off; every answer is measured and logged.
- **Interfaces (FR-18 to FR-21).** Chat with code answered in it, the Code agent, the live view of the model at work, the pairing that gives other runtimes memory as words, and the event log.
- **The proof (FR-22 to FR-26).** The Long Haul is built from a seed, cut and sampled; every contender is told and asked the same; answers are graded by rule; the cloud yardstick is metered; every run writes a dated record.
- **The assistant (FR-27 to FR-32).** Questions are routed to memory or to the model's own knowledge; research, files and revision feed topic shelves; and memory can be switched between CAMR, RAG and off to compare them.

Table: {#fr} Functional requirements catalogue

| ID | Requirement | Priority | Source | Verification |
|---|---|---|---|---|
| FR-01 | The baseline shall turn each document into notes under a configurable write policy (verbatim or structured). | Must | ii; v1; P §3.5.5 | T |
| FR-02 | The baseline shall reject empty, duplicate and instruction-like notes and record each rejection with its source. | Must | ii; v1; P §3.3 | T |
| FR-03 | The baseline shall retrieve the k notes most similar to a question and rank them by similarity alone or by Equation {eq:composite}. | Must | ii; v1; P §3.5.1 | T |
| FR-04 | The baseline shall admit candidates by the gate of Equation {eq:gate} and add notes about entities named in admitted notes. | Must | ii; v1; F1, F1b | T, M |
| FR-05 | The baseline shall pack admitted notes into a token budget and never exceed it. | Must | ii, v; v1; P §3.5.1 | T |
| FR-06 | The baseline shall run floor, ceiling and treatment conditions on one fixed sample and compute the gap closed (Equation {eq:gap}). | Must | iv; v1; P §3.5.2 | T |
| FR-07 | The engine shall remember a moment by having the frozen reader read it once, with its room's earlier moments in view, and saving the keys and values of every layer. | Must | ii; E; E-15 | T, M |
| FR-08 | The engine shall place each new moment in a room by Equation {eq:room}. | Must | ii; E; E-18 | T |
| FR-09 | The engine shall append a moment's notes to its room's file and keep its words, day, room and embedding in an index. | Must | ii, iii; E; `rooms.py` | T |
| FR-10 | The engine shall write each moment as a Markdown note in a vault, with links (doors) to notes it shares a room or an answer with, and a strength that fades each day it is unused (Equation {eq:fade}). | Should | ii; E; E-29; `vault.py` | T |
| FR-11 | The engine shall keep recently used rooms in RAM under a RAM budget, and put the weakest rooms to sleep, keeping their words, when the room files outgrow a disk budget (Equation {eq:budget}). | Must | iii; E; E-29; `swap.py` | T, M |
| FR-12 | For each question, the engine shall lay on the desk the room holding the moment closest to the question, after the header and the core, and then let the reader read the four closest moments as words, in date order. | Must | ii, v; E; E-16 | M |
| FR-13 | The engine shall read a room from RAM when it is hot, from the SSD in one burst when it is awake, and as words (or woken) when it is asleep. | Must | iii; E; `swap.py` | T |
| FR-14 | The engine shall build a core of at most 256 tokens from vault notes tagged `core` and keep it in RAM as notes. | Could | ii; E; `core.py` | T |
| FR-15 | A session shall read several reaches (session, project, agent, global) and write to one; a question shall choose the best room over every reach it reads. | Must | v; E; E-42; `reach.py` | T, M |
| FR-16 | A session shall let memory be switched off, so that the plain model answers with the same prompt and no notes. | Must | iv; E; `reach.py` | T |
| FR-17 | The engine shall record for every answer its time to the first word, total time, retrieval time per step, tier, bytes read, tokens in context, history held, peak RAM and disk (Table {tab:metrics}). | Must | iv; E; `metrics.py` | T |
| FR-18 | The application shall offer Chat, in which a user tells, asks and requests code, which is returned as formatted code blocks; the Code agent used in the Code benchmark shall run every shell command only after the user's approval. | Must | iii; E; E-50 | D |
| FR-19 | The application shall show, only as the engine measures them and only when the user asks, the model's layers loading, the room an answer reads and where it came from, and each layer's activity for each word. | Should | ii; E; `live.py` | D, T |
| FR-20 | A pairing proxy shall give Ollama, and any OpenAI-compatible local server, memory as words: the closest notes in front of the last user message. | Should | iii; E; E-33, E-47 | T |
| FR-21 | The engine shall log each remember, answer, sleep and wake as one line, with each written word's attention over the moments on the desk. | Should | ii; E; E-21 | T |
| FR-22 | The Long Haul shall be generated deterministically from its seed and cut at fixed sizes, each cut asking a stratified sample of 10 questions per family (all 3 for the page). | Must | iv; E; E-30 | T |
| FR-23 | Every contender shall be told the history one event at a time and asked the same questions with the same instructions; asking shall never teach. | Must | iv; E; E-31, E-32 | T, I |
| FR-24 | Every answer shall be graded by rule into one of five verdicts (Table {tab:verdicts}). | Must | iv; E; `haul/grade.py` | T |
| FR-25 | Every call to the cloud yardstick shall be logged with its tokens and cost, and refused if its worst case would pass the night's cap. | Must | iv; E; `bench/claude.py`, `bench/cost.py` | T |
| FR-26 | Every run shall write a dated record after every checkpoint, naming the machine, its load, the code fingerprint and every answer. | Must | iv; E; E-12, E-40 | T, I |
| FR-27 | The assistant shall route each question, by the model's one-word answer, to memory or to the model's own knowledge, and send a question naming a person or business found in its closest notes to memory. | Must | ii; E; E-55; `assistant.py` | T |
| FR-28 | Research shall read a Wikipedia page as marked data in the user's turn, never as instructions, and keep what it learns on the Research shelf, marked as from the web. | Should | iii; E; E-55; `assistant.py` | T |
| FR-29 | Attached PDFs, images and videos shall be turned into words once (images and frames by a vision model) and kept on a shelf, marked as from a file. | Should | ii; E; E-44, E-57; `media.py` | T, M |
| FR-30 | Before a moment is kept, a close earlier moment of the same source shall be judged SAME, UPDATE or NEW; an updated note is kept and the old one marked superseded, never deleted. | Should | ii; E; E-56; `revise.py` | T |
| FR-31 | The application shall keep memory on topic shelves (Projects, Coding, Research, Personal), file a moment on "Auto" by meaning, and read every shelf for a question. | Should | v; E; E-51; `shelves.py` | T, D |
| FR-32 | Chat shall answer a question with CAMR's memory, with conventional RAG over the same memory or with no memory, as the user chooses, and a Compare action shall answer it all three ways with each answer's measured first word and text read. | Should | iv; E; `chat.py` | T, D |

### Non-Functional Requirements

Non-functional requirements describe how well the system must operate and the constraints under which it must work. They use the ISO/IEC 25010:2023 characteristics relevant here (performance efficiency, reliability, security, maintainability, flexibility) and add model quality and honesty for the AI components (Table {tab:nfr}). A requirement later measured as not met is kept as written, so that Chapters 5 and 6 report it honestly.

Table: {#nfr} Non-functional requirements catalogue

| ID | Category | Requirement | Priority | Source | Verification |
|---|---|---|---|---|---|
| NFR-01 | Performance: time | With 2,000 words in the room on the desk, read from the SSD with the cache bypassed, the median time to the first word shall be under 0.5 s. | Must | iii, v; E; E-19 mark 1 | M |
| NFR-02 | Performance: time | At 2,000 words, answering from notes shall be at least 10 times sooner than reading the same desk as words. | Should | iii; E; E-19 mark 3 | M |
| NFR-03 | Performance: capacity | As the memory grows, the median time to the first word and the peak RAM shall not climb. | Must | iii, iv; E; E-20, E-38 | M |
| NFR-04 | Performance: resources | The room files shall stay within a disk budget (40 GB in the benchmarks; 8 GB per shelf in the app) and the hot rooms within a RAM budget (2 GB in the benchmarks; 512 MiB by default). | Must | iii; E; E-54; `swap.py` | M |
| NFR-05 | Performance: resources | MLX's cache of freed graphics buffers shall be capped (1 GB by default), and every record shall log the process's real footprint. | Must | iii; E; E-40, E-41 | M |
| NFR-06 | Performance: time | Retrieval shall take at most 10% of answer time on the target device. | Should | iii, v; v1; F8 | M |
| NFR-07 | Model quality | Within one room, notes shall know at least 95% as many facts as the same desk read as words, with at most 3 extra false memories of 45. | Must | ii, iv; E; E-19 mark 2 | M |
| NFR-08 | Honesty | Answers about things never told shall be graded separately; a decline is right and a guess is a false memory. | Must | iv; E; E-08, E-30 | T |
| NFR-09 | Reliability | Local contenders in the benchmarks shall decode greedily with thinking off, so that re-runs give the same verdicts. | Must | iv; E; E-10, E-41 | I, M |
| NFR-10 | Security: privacy | All local inference and memory shall stay on the Mac once the models are downloaded; only research and the yardstick's benchmark runs reach a network service, and the yardstick sends scripted text only. | Must | iii; E; P §1.6 | I |
| NFR-11 | Security: integrity | The engine's server and proxies shall listen on 127.0.0.1 only, answer only requests that name the local host, and refuse requests from web pages; the app's server shall require the token made at launch. | Must | iii; E; `app/server.py`, `pair/ollama.py`, `Engine.swift` | T |
| NFR-12 | Security: integrity | A reach folder shall be opened by one process at a time, and rooms written for one model shall not open with another. | Must | ii; E; `reach.py`, `rooms.py` | T |
| NFR-13 | Reliability: measurement | Only one measuring job shall use the graphics processor at a time, and the app shall pause while a benchmark measures. | Must | iv; E; E-35 | I |
| NFR-14 | Cost | The yardstick's spending shall stay under $60 a night, with $2 of headroom held for the worst case of the next call. | Must | iv; E; E-29; `bench/claude.py` | T, M |
| NFR-15 | Maintainability: testability | Every reported number shall be regenerable from records that carry a fingerprint of the code that made them. | Must | iv; both; P §3.7.2; E-12 | T, I |
| NFR-16 | Flexibility: adaptability | The tests that need no MLX shall run on Linux on every push. | Should | iv; E; `tests.yml` | T |

### Data Requirements

Data requirements describe the data the system needs, produces, protects and retains (Table {tab:dr}). Neither stage trains the language model, so the separation of development and test data applies to the engine's settings and to the questions. In the baseline, settings were tuned on validation questions and confirmed once on held-out ones (F13, F15). In the rooms build, the development lives (seed 0) were used to choose the room design, and the proof lives (seed 1) were run only after the pass marks were written (E-19). In the final engine, no setting was tuned on the Long Haul: the room design came from the lives, and the instructions were fixed before any Long Haul result (E-32, E-37).

The Long Haul is synthetic by design. A memory that grows over months cannot be tested on a public question set, while a script knows its right answer on every day, including after a fact changes. It uses Kenyan names and places, which suits the intended users but limits the results to one invented project; the public suites are the real-data complement. No personal data enters any evaluation, and a user's own memory never leaves the Mac.

Table: {#dr} Data requirements catalogue

| ID | Requirement | Priority | Source | Verification |
|---|---|---|---|---|
| DR-01 | The baseline shall use the official PopQA, HotpotQA, 2WikiMultiHopQA and GSM8K files, and its memory shall come only from supporting and distractor documents. | Must | iv; v1; P §3.2 | I, T |
| DR-02 | The Long Haul for seed 1 shall hold 17,786 events and 2,010,094 tokens over 110 working days, extended to 4.01M tokens with noise only, every probe unchanged. | Must | iv; E; E-30, E-39 | T |
| DR-03 | Each checkpoint shall sample 10 askable probes per family with seed 0; a cut where nothing new is askable shall reuse the sample before it. | Must | iv; E; E-30, E-39 | T |
| DR-04 | Each moment shall carry its date and the Long Haul's day number, as `[YYYY-MM-DD, day N] text`. | Must | iv; E; `bench/local.py` | I |
| DR-05 | Each moment shall be stored as words in the index, an embedding row, notes in its room's file and a vault note whose tags record its source (user, file or web). | Must | ii; E; `rooms.py`, `vault.py` | T |
| DR-06 | Room files shall only grow while awake; sleep shall delete a room's notes but never its words, and a superseded note shall be kept. | Must | ii; E; `swap.py`, `revise.py` | T |
| DR-07 | Every record shall name the machine, chip, memory, power, load, library versions, commit and a hash of the code. | Must | iv; E; E-12, E-17 | I, T |
| DR-08 | Personal memory and saved conversations shall stay in folders under `~/.camr/` on the user's Mac. | Must | iii; E; `reach.py` | I |

### Interface and Integration Requirements

Interface and integration requirements describe how the user, the models and outside services meet the system. They are kept narrow so that each can be tested: the app reaches the engine only through a small JSON API on the loopback address, the models are loaded in-process through MLX, and outside services are reached only by research and the benchmark runners (Table {tab:ir}).

Table: {#ir} Interface and integration requirements catalogue

| ID | Requirement | Priority | Source | Verification |
|---|---|---|---|---|
| IR-01 | The baseline shall reach local models only through Ollama on the loopback address, and the cloud model under one pinned, logged identifier. | Must | iii, iv; v1; P §3.6 | T |
| IR-02 | The engine shall load its models through MLX and refuse a reader whose layers do not all keep keys and values with plain rotary positions. | Must | iii; E; E-26, E-44; `notes.py` | I |
| IR-03 | The engine shall read and write room files with the file cache bypassed (`F_NOCACHE`), in 1 MB pieces eight at a time. | Must | iii; E; E-14 | T, I |
| IR-04 | The Mac app shall start the engine as a local process on a free port, send the token only after the engine reports holding that port, and use only the engine's JSON routes. | Must | iii; E; `Engine.swift` | D, T |
| IR-05 | The engine's server shall return failures as JSON (403, 404, or 500 with the error) instead of dropping the connection. | Should | iii; E; `server.py` | I |
| IR-06 | The Ollama pairing shall speak Ollama's own HTTP API on 127.0.0.1:11435 and forward everything else byte for byte to 11434. | Should | iii; E; E-33 | T |
| IR-07 | The OpenAI-compatible endpoint shall serve `/v1/` routes on 127.0.0.1:11436 in front of Ollama, LM Studio or mlx_lm.server. | Could | iii; E; E-47 | T |
| IR-08 | The yardstick runner shall stream every request, turn the SDK's retries off and never ask for a fallback model. | Must | iv; E; `bench/claude.py` | I |
| IR-09 | Models and suites shall be loaded from the Hugging Face Hub once and read from a local folder afterwards. | Must | iv; E; `bench/suites` | I |
| IR-10 | Research shall fetch only Wikipedia's public API over HTTPS, with a fixed timeout, and shall fail with a message rather than an answer when the page cannot be read. | Should | iii; E; `assistant.py` | T |

### Requirements Traceability

Every requirement links back to an objective and forward to a design element and to the evidence that verifies it (Table {tab:trace}). Objective i is met mainly by Chapter 2, but it also shaped the system: the reviewed techniques were built as switchable choices so that their value could be measured.

Table: {#trace} Traceability matrix

| Objective | Requirements | Design elements | Verification evidence (Chapter 5) |
|---|---|---|---|
| i. Techniques and limits | FR-03, FR-04, FR-07, FR-12 | Baseline read path (Equations {eq:composite} and {eq:gate}); room design (Figure {fig:arch}) | Baseline results; development evidence of the rooms build |
| ii. Design | FR-07 to FR-14, FR-21, FR-27 to FR-30, DR-05, DR-06, NFR-07 | Memory, Rooms, Notebook, Tiers, Vault, Core, Event log, assistant (Figures {fig:arch} to {fig:files}) | Unit tests; test cases T-08, T-19 to T-21; rooms-build results |
| iii. On the device | FR-11, FR-13, FR-18 to FR-20, FR-31, NFR-01 to NFR-05, NFR-10 to NFR-13, IR-02 to IR-04 | Tiers; deployment (Figure {fig:deployment}); the app | Test cases T-02 to T-07, T-11, T-12, T-15; speed and RAM results |
| iv. Evaluation | FR-06, FR-16, FR-22 to FR-26, DR-01 to DR-04, DR-07, NFR-08, NFR-09, NFR-14, NFR-15 | Evaluation pipeline (Figure {fig:pipeline}) | Long Haul, suites, multimodal and Code results; T-09, T-10, T-13, T-14, T-17 |
| v. Budget and components | FR-05, FR-08, FR-12, FR-15, FR-31 | Rooms of 512 tokens, join 0.80, four closest moments; reach; shelves | Desk and room-size comparisons; reach; notes against words; storage at 8 and 4 bits |

## System Analysis Diagrams {#analysis-diagrams}

This section presents the diagrams used to analyse the system's boundary, its actors and services, and the workflow of its evaluation. Each is introduced by what it shows and why it is needed, and interpreted after the figure.

### Context Diagram

The context diagram treats CAMR as one process and shows only what crosses its boundary. It fixes the scope of Section {sec:scope}, in which the model and the memory run on the user's Mac, and shows which flows leave it (NFR-10, DR-08). It uses Gane–Sarson notation: CAMR is process 0, each shaded box is an external entity and each labelled arrow is a data flow; flows that exist only in the baseline are dashed.

![{#context} Context diagram of CAMR](diagrams/context.png)

The user's moments, files and questions flow into CAMR and their answers flow back, and nothing the user tells continues to an outside party. The flows that leave the Mac carry no personal memory. The Hugging Face Hub supplies model weights and the public suites once; afterwards they are read from the local cache. The Anthropic API receives the scripted Long Haul and the suites' questions, and only when the researcher runs the yardstick. Ollama is outside the boundary because it is a separate program that the pairing reaches over the loopback address; the engine's own models run inside its process. The diagram therefore presents CAMR in use as a closed system on the Mac, the privacy property that the problem statement requires.

### Use Case Diagram

The use case diagram shows who uses CAMR and for what (Figure {fig:usecases}). Its actors are people and external systems only: the User, the Researcher, the Ollama command line and the Claude API. Rooms, the embedder and the event log are internal parts and are not actors. «include» and «extend» relations are dashed arrows, and generalisation is a hollow triangle.

![{#usecases} Use case diagram of CAMR](diagrams/use_cases.png)

"Recall from memory" is included by every use case that answers: chatting, asking for code in Chat, comparing CAMR with RAG, the Ollama pairing and the abstract "Run a benchmark", which the Long Haul and the suites specialise. One read path therefore serves chat, agentic work and evaluation, so what is measured is what the user gets. Choosing the memory mode (CAMR, RAG or off), comparing the three, and choosing a reach or shelf extend chatting. Asking Claude alone extends a benchmark: the yardstick answers the same questions with no memory. Watching what an answer reads, and browsing the vault, are a user's use cases rather than research tools only: they let a user see when an answer rested on the wrong moment.

### Use Case Descriptions {#uc-desc-section}

Table {tab:ucdesc} describes the main use cases of Figure {fig:usecases}: the actor, the trigger, the main flow, the alternative and exception flows, and the requirements each realises.

Table: {#ucdesc} Use case descriptions

| Use case | Actor and trigger | Main flow | Alternatives and exceptions | Requirements |
|---|---|---|---|---|
| Tell or attach something to remember | User: types a moment or attaches a file | The moment is dated, judged against its closest earlier moment, filed on its shelf, read once by the model and kept | Same as a kept moment: not kept again. Updates a moment: kept, old one marked superseded. File: turned into words first; a picture needs the vision model, which is downloaded once | FR-07 to FR-10, FR-29 to FR-31 |
| Chat: ask, or research online | User: sends a question | The question is routed; a memory question reads its room and closest moments and is answered; a general one is answered from the model's knowledge; the exchange is kept | Memory off: the model answers alone. Room asleep: read as words. Research: a page is fetched and read as data; no page found: the user is told. Stop: the answer ends at the next word | FR-12, FR-13, FR-16, FR-27, FR-28 |
| Ask for code in Chat | User: asks for a function, a page or a fix | The question is routed to the model's own answer with enough room for code; the code is shown as formatted blocks with a Copy button, and the exchange is kept on a shelf | A question naming the user's own project reads memory first. Stop: the answer ends at the next word | FR-18, FR-27 |
| Compare CAMR, RAG and off | User: asks a question with Compare | The question is answered three times, from CAMR's room already read, from the closest moments pasted as text, and with no memory; each answer shows its first word, text read and the room or chunks used | Compare answers are not kept in memory; the conversation is not used, so the three see the same question | FR-32 |
| Watch what an answer reads | User: opens the weights view | The view draws the layers loading, the room read and each layer's activity for each word, from the engine's live events | No events: nothing moves | FR-19 |
| Pair Ollama with memory | Ollama command line: sends a chat | The proxy recalls the closest notes, puts them before the last user message and forwards the chat; the exchange is remembered afterwards | Any other route is forwarded unchanged | FR-20, IR-06, IR-07 |
| Run the Long Haul | Researcher: starts a run | Each contender is told the history, asked each checkpoint's questions read-only, graded by rule, and a dated record is written | Claude: a call whose worst case passes the cap is refused. A second measuring job waits | FR-22 to FR-26 |

### Activity Diagram: The Evaluation Pipeline {#pipeline-section}

The study's contribution is a measurement, so the workflow that produces each number is analysed as carefully as the engine. Figure {fig:pipeline} shows the Long Haul's pipeline as a UML activity diagram.

![{#pipeline} The evaluation pipeline of the Long Haul](diagrams/evaluation_pipeline.png)

The script is built once from its seed and cut at fixed sizes; at each cut, a checkpoint samples the questions that can be asked there. The pipeline then forks into one branch per contender. Each local contender is told the history one event at a time and then asked the checkpoint's questions, read-only. The yardstick instead reads the newest part of the history that fits its window, with every request held against the cost ledger before it is sent. The branches join at grading, which applies the same rules to every answer, and every checkpoint writes a dated record before the next cut is told. What is held constant is what makes the scores comparable: the same events, the same questions, the same instructions and the same grader for every contender (E-32). What differs is only what each contender can see.

## System Design Diagrams {#design-diagrams}

This section describes how the solution is organised to satisfy the analysed requirements: the architecture of the baseline and of the engine, the engine's classes, the assistant around it, the handling of one question, the life cycle of memory, the stored data and the deployment.

### Architecture of the Baseline, CAMR v1

CAMR v1 has a write path and a read path that meet at one SQLite file, whose tables Figure {fig:schema} shows. Ranking follows Park et al. (2023), with similarity and importance normalised over the candidates and recency counted in question steps (Equation {eq:composite}); the gate then decides how much of the ranked list the model sees (Equation {eq:gate}).

$$\text{score}(n) = w_s\,\hat{s}(n) + w_r\,\gamma^{\Delta t(n)} + w_i\,\hat{\imath}(n)$$ {#composite} [Composite score of a note (baseline)]
Equation {eq:composite} is the composite score of note n (defaults \(w_s = 0.60\), \(w_r = 0.15\), \(w_i = 0.25\), \(\gamma = 0.99\); similarity only sets \(w_s = 1\), \(w_r = w_i = 0\)).

$$n \text{ is admitted} \iff s_{\max} \ge \tau \ \text{ and } \ s(n) \ge s_{\max} - \delta$$ {#gate} [The gate (baseline)]
Equation {eq:gate} is the gate, where \(s_{\max}\) is the best candidate's similarity (defaults \(\tau = 0.50\), \(\delta = 0.15\)).


On the read path, the gate and entity bridging make the read path capability-adaptive: the gate admits fewer notes when the best match is weak, and bridging adds the notes about entities that admitted notes name, which finds the second hop of a question without a graph. The model is reached only through a loopback runner, and the cloud only in ceiling conditions or on escalation. Similarity became the default ranking after the composite score was measured (Section {sec:baseline-results}; Table {tab:changes}).

### Architecture of CAMR {#arch-section}

CAMR changes what a memory is. Instead of text that the model must re-read for every question, each moment is kept as the notes the model wrote while reading it: the keys and values of every layer, which a transformer normally discards after a prompt. Laid in front of the model, they let it continue as if it had just read the moment. Notes are large (Equation {eq:bytes}), so they live on the SSD in rooms of related moments that are written as one continuous page and fetched in one read. A moment joins a room by Equation {eq:room}. The application calls a room a "note" and groups memory by topic on "shelves" (Section {sec:assistant-design}); this thesis keeps "room" for the engine's unit.

$$\text{room}(m) = \text{room}\Big(\underset{k\,:\ s_{mk} \ge J,\ T_{\text{room}(k)} + t_m \le T_{\max}}{\mathrm{arg\,max}}\ s_{mk}\Big), \ \text{ else a new room}$$ {#room} [Room placement of a new moment]
In Equation {eq:room}, \(m\) is the new moment with \(t_m\) tokens, \(s_{mk}\) is its similarity to an earlier moment \(k\), and \(T\) is a room's tokens (\(J = 0.80\), \(T_{\max} = 512\); E-18).

$$b_{\text{token}} = L \times 2 \times H_{kv} \times d_h \times 2 \text{ bytes}$$ {#bytes} [Notes per token]
Equation {eq:bytes} gives the notes per token, for \(L\) layers, \(H_{kv}\) key–value heads, head size \(d_h\) and 16-bit values: 28 × 2 × 8 × 128 × 2 = 114,688 bytes for Qwen3-1.7B and 36 × 2 × 8 × 128 × 2 = 147,456 bytes for Qwen3 4B and 8B. A full room of 512 tokens is therefore 56 MiB for the 1.7B, about 29,000 times its text. To keep the SSD smaller, a room can also be stored at 8 or 4 bits, quantised in groups of 64 values, which takes 17/32 or 9/32 of its 16-bit size; each room's precision is recorded in the index, so rooms of different precisions can be read side by side.

![{#arch} Component diagram of CAMR, the final engine](diagrams/architecture.png)

Each component has one responsibility (Figure {fig:arch}). Rooms owns the room files and the index and knows nothing about models. The Notebook turns tokens into notes and notes into a desk, and is the only part that touches the reader's cache. The Tiers decide where each room's notes are: hot in RAM, awake on the SSD, or asleep as words. The Vault keeps every moment as a Markdown note that a person can open in Obsidian, with links between notes that are used together and a strength that fades (Equation {eq:fade}). The Core holds a few standing facts as notes in RAM. The Event log watches attention without changing it, Metrics times every step, and Live reports what a person can watch. Memory composes them into remember, choose, recall, answer and fade, and a Session composes one Memory per reach. The app, the Code agent, the pairing and every benchmark runner call the same Session or Memory, so the read path that is measured is the one the user meets.

$$s_{n}(d) = s_{n}(d_0)\times 0.95^{\,d-d_0} + u_n$$ {#fade} [Strength of a vault note]
In Equation {eq:fade}, a vault note's strength \(s_n\) on day \(d\) is its strength on the day \(d_0\) it was last brought up to date, reduced by 5% for each day unused, plus 1.0 for each of its \(u_n\) uses since then; a note at strength 1 that goes unused for about 45 days falls below 0.1 and counts as faded. Pinned notes never fade, and nothing is ever deleted by the engine. A room is as strong as its strongest note, and when the room files outgrow the disk budget the weakest room sleeps first (Equation {eq:budget}).

$$\text{while}\ \sum_{r \in A} S_r > B_{\text{disk}}:\quad r^{*} = \underset{r \in A}{\mathrm{arg\,min}}\ \left(\sigma_r,\ \tau_r\right)\ \text{sleeps}$$ {#budget} [The disk budget rule]
In Equation {eq:budget}, \(A\) is the set of awake rooms, \(S_r\) the size of room \(r\)'s notes file, \(B_{\text{disk}}\) the disk budget, \(\sigma_r\) the room's strength (that of its strongest vault note) and \(\tau_r\) the time it was last used; sleeping deletes the room's notes file and keeps its words.

Two findings from the development lives fixed the shape of a room and of the desk (E-15, E-16; Section {sec:rooms-results}). Moments written alone and laid side by side lost the thread for a small reader, so a room is written as one page, each moment read with the room's earlier moments in view. And one room plus the four closest moments as words knew more facts than either alone or than three rooms, so that is the desk. A single room sits where it was written, so its keys need no turning; with the core before it, a room sits further along the desk and its keys are turned by the core's length (Su et al., 2024).

### Class Diagram of the Engine {#class-section}

The component diagram shows responsibilities; the class diagram shows the classes that carry them, with their main attributes and operations and the relationships between them (Figure {fig:class}). It is drawn from the engine's code, so its names are those of the implementation.

![{#class} Class diagram of the CAMR engine](diagrams/class_engine.png)

A Session holds the reaches it reads and aggregates one Memory per reach, so a question can be answered over several memories while each keeps its own folder. Memory is the centre: it is composed of its Rooms, and of a Vault and Tiers when they are enabled, which live and die with it, while it only aggregates a Notebook and a Core, because the Session builds one Notebook and shares it across every Memory, and a Core can be handed in from outside. Memory is associated with exactly one Reader and one Embedder, the frozen models, which it uses but never changes. Rooms knows nothing about models: it places a moment, appends its notes and fetches whole rooms, and Tiers is bound to it to decide where those notes are. The Notebook is the only class that touches the Reader's cache, writing notes and laying the desk. The Sorter files a moment onto one of the Shelves by the Embedder's closeness, and a Shelf names the Reach it is kept in. The assistant and revise are modules of functions rather than classes: they use the Reader, Rooms and the Embedder through a Memory and add no state of their own, which is why the engine is unchanged when the assistant is not used. Reader reports what it does to a Live only when a Live listens, and the vision model, Seer, stands apart: only the application's chat route uses it, to turn a picture into words before they are remembered.

### The Assistant: Routing, Research, Files, Revision and Shelves {#assistant-design}

In its final form the chat is an assistant built around the engine, as a set of components that reach memory only through a Session (Figure {fig:arch} shows the engine they use). It keeps the conversation and answers from the model's own knowledge, and it reaches into memory only when a question needs it. The closeness of the nearest memory cannot tell such questions apart, since a greeting can sit as close to a remembered moment as a question about the user's records. The design therefore lets the model route each question itself, with a one-word answer, MEMORY or GENERAL, that reads the question, the last two turns and the closest note in memory; a question that names a person or business found in its closest notes goes to memory without asking the model (FR-27; E-55). Only a MEMORY question fetches a room, and the router's word is never shown.


Five parts surround the router. Research looks a question up on Wikipedia (a search, then the best page's plain text); the page goes into the user's turn between markers as data, never into the instructions, and what is kept from it goes on the Research shelf marked as from the web (FR-28). Files are turned into words once: a PDF a page at a time as its text, and images and video frames by a vision model that also reasons, before the words are kept like any other moment, marked as from a file and not as the user's words (FR-29; E-57). Revision compares a new moment with the closest moment of the same source; only a close pair is judged by the model, in one word, SAME, UPDATE or NEW, and an update keeps the new moment and marks the old one superseded, never destroying it (FR-30; E-56). Shelves give the memory topics (FR-31; E-51): Projects is the global reach, which every session reads, and Coding, Research and Personal are project reaches, each with its own rooms and vault. A question reads every shelf and the closest moment wins; when another shelf's closest moment is nearly as close, it is read as well. A new moment goes on the shelf the user picks or, on "Auto", on the shelf whose description and examples it is closest to by the same embedder, so it is filed by meaning. When a session opens, a warm-up builds the model's kernels and reads the newest rooms of every shelf, up to 1.5 GB, so that the first questions find them in RAM (E-52). Finally, a memory mode lets the same question be answered with CAMR's memory, with conventional RAG over the same memory (the closest moments pasted in as text) or with no memory, and a Compare action asks it all three ways, so the difference between the pipelines can be seen on any question (FR-32). The design keeps the engine unchanged: every part reaches memory through a Session, so routing, research and files cost nothing when they are not used.

### Sequence Diagram: One Question {#sequence-section}

Figure {fig:sequence} follows one question asked in Chat. Lifelines run left to right and time downwards; solid arrows with filled heads are calls, dashed arrows with open heads are returns, a looping arrow is work done inside one part, and a bar shows while a part is busy. The diagram realises FR-12, FR-13, FR-17 and FR-19, and shows where the wait of NFR-01 and NFR-03 is spent.

![{#sequence} Sequence diagram of one question answered in Chat](diagrams/sequence_question.png)

The order of steps keeps the wait short. The question is embedded once, and the closest moment is chosen over every reach the session reads. The room is then fetched before the reader writes anything: from RAM when hot, in one SSD burst when awake, or as words when asleep. The header and the core are already notes in RAM, and the room arrives already read, so at question time the reader reads only the four closest moments, the date and the question as words. While the answer is written, the app polls the live events and draws each word and each layer's activity. Every answer ends with one metrics record and one line in the event log. Because the desk is always one room and four moments, the work done before the first word does not depend on how much the memory holds; Chapter 5 measures this (Section {sec:speed-results}).

### State Machine Diagram of a Room and Its Moments {#states-section}

A moment and its room have coupled life cycles: placing a moment changes its room, a question moves a room onto the desk, and the disk budget can put a room to sleep. Figure {fig:states} shows the three state machines; its guards are Equations {eq:room}, {eq:share} and {eq:fade}.

$$\text{share}_j = \frac{\sum_w a_{wj}}{\sum_w \sum_k a_{wk}}, \qquad j \text{ is used} \iff \text{share}_j \ge 0.10$$ {#share} [Share of the desk's attention drawn by a moment]
Equation {eq:share} is the share of the desk's attention drawn by moment \(j\) over an answer, where \(a_{wj}\) is the attention from written word \(w\) to \(j\)'s tokens, averaged over every head of layers 12, 16, 20 and 24 (E-21).

![{#states} State machines of a moment, a room and a vault note's strength](diagrams/state_room.png)

A moment has no final state: once stored it only cycles between Stored and On the desk, where it is either used or only picked up. A room is awake on the SSD, hot in RAM after a read, and back to awake when it is the least recently used room and the RAM budget is full; letting a hot room go writes nothing, since its file is still on the SSD. When the awake room files outgrow the disk budget, the weakest room goes to sleep: its notes file is deleted and its moments stay as words in the index and the vault. A question about an asleep room reads its moments as words, or wakes it when waking is on, which costs one reading of the room by the model. Sleep therefore keeps the SSD within its budget without destroying anything the user told.

### Logical Schema of the Baseline Store

The baseline uses an embedded relational database, so a logical schema is the right view. Figure {fig:schema} shows its tables with their keys and cardinalities.

![{#schema} Logical schema of the baseline's store](diagrams/schema_v1.png)

The integrity rules carry the baseline's guarantees. Checksums are unique, and a source is unique per dataset, document and note type, so each write policy is its own note population in one file. A note and its embedding are committed together with a cascading delete, so no note lacks its vector. `meta` records the schema version, embedder and dimension, and a store refuses an embedder it was not built with.

### File and Data Design of CAMR {#files-section}

CAMR has no transactional database, so a relational schema would misrepresent it. Each memory is one folder in which every file has one writer and one format, and each reach or shelf is a folder of its own under `~/.camr/` (Figure {fig:files}, Table {tab:files}).

![{#files} Files of a CAMR memory, its reaches and its records](diagrams/files.png)

Table: {#files} Files of a CAMR memory

| File | Format | Written | Read |
|---|---|---|---|
| `room-NNNNNN.notes` | Raw 16-, 8- or 4-bit values, token by token (tokens × layers × keys and values × heads × head size) | Appended at each remember; deleted when the room sleeps | Whole, at recall, cache bypassed |
| `index.json` | Every moment's words, day, room and byte range; every room's members, tokens and precision | After each moment in a shared reach; at save | When the memory opens; for the words a desk re-reads |
| `vectors.npy` | float32 matrix, one unit row per moment | With the index | On opening; one product per question |
| `vault/*.md` | One Markdown note per moment: front matter (id, day, room, reach, strength, tags, links, doors), then its words | At each remember, fade and revision | By a person (Obsidian); by the core, sleep and revision |
| `events.jsonl` | One JSON line per moment kept, answer given, room put to sleep or woken | At every event | The app's views |
| `metrics.jsonl` | One JSON line per answer (Table {tab:metrics}) | At every answer | Summaries; the app |
| `tiers.json` | When each room was last used | With the index | When the memory opens |
| `.lock` | A lock held while a process has the folder open | On opening a reach | By a second process, which is refused |
| `chats/<id>.json` | One saved conversation: its turns and the shelf each answer read | After each answer | When a conversation is reopened |

Files suit a workload with two operations: append a moment's notes to one file, and read one whole file. Each room is a contiguous array read in one burst, with no lookup and no database page cache in between, and bypassing the file cache makes every recall a real SSD read. The readable part of memory sits in a small index and the vault, which can be inspected without touching the notes. Files refer to each other by integer position: a moment's id is its row in `vectors.npy`, and its byte range in the room comes from the index. The notes' size per token, recorded in the index, stops another model from opening the memory (NFR-12).

Table: {#metrics} What every answer records

| What | Field | How it is counted |
|---|---|---|
| Time to the first word | `first_word_s` | From the question to the first word: choosing, reading the room, laying the desk and reading the words all count |
| Total time | `total_s` | From the question to the last word |
| Prefill and decode speed | `prefill_tps`, `decode_tps` | Tokens read as words per second before the first word; tokens written per second |
| Retrieval time | `retrieval_ms` | Per step: choose, core, fetch (the SSD read), wake, desk, and total |
| Where the room came from | `tier` | RAM, SSD or vault (asleep) |
| Bandwidth | `read_bytes`, `gbps` | Bytes read from the SSD for this answer, and how fast |
| Context and history | `context_tokens`, `history_tokens` | Every token the model saw; every token the memory holds over every reach read |
| Peak RAM and footprint | `peak_ram_bytes`, `peak_mlx_bytes`, `footprint_gb` | The process's peak resident memory and MLX's own peak; in the benchmarks, the process's physical footprint per checkpoint |
| Disk | `disk_bytes` | The memory folders on disk: room files, indexes, logs and vaults |

### Deployment Diagram {#deployment-section}

Figure {fig:deployment} shows where each part of CAMR runs: one Mac, its execution environments, the files on its SSD, and the outside parties that are used once, for research, or for benchmarks only.

![{#deployment} Deployment diagram of CAMR on the Mac](diagrams/deployment.png)

The Mac app is a SwiftUI process that starts the engine as a second, Python process with the chosen model and a token made at launch, and talks to it only over the loopback address (IR-04). The engine holds the reader, the embedder and, when a picture needs it, the vision model in unified memory through MLX on the graphics processor; each model has its own memory folder, because notes belong to the model that wrote them. Ollama, when paired, is a third process that the proxy reaches on its own port. The Hugging Face Hub is contacted only when a model or suite is missing, Wikipedia only when the user asks for research, and the Anthropic API only by the yardstick's runner, with its key read from a private file and never logged. GitHub Actions runs the tests that need no MLX on every push (NFR-16).

## Design Changes Since the Proposal {#changes}

Building and measuring the three stages changed several choices that the proposal had fixed in advance. Table {tab:changes} states each change and the evidence for it, so that the diagrams, the code and the report describe the same system.

Table: {#changes} Changes from the proposed design

| Proposed | Built | Reason and evidence |
|---|---|---|
| An embedded database: SQLite with a vector extension in one file (P §3.6.5; objective iii) | The baseline as proposed; the engine stores one append-only file per room on the SSD, an index, a vector file and a vault | The engine stores the model's notes, 114,688 to 147,456 bytes per token (Equation {eq:bytes}), and only appends and reads whole files; bypassing the cache gives honest SSD timings (E-14) |
| Short structured notes of the text (P §3.5.1) | The model's own keys and values, read back as if just read | Reading notes back skips re-reading the text, and within one room notes answered as the words did (E-20; Section {sec:rooms-results}) |
| A 16 GB laptop with no dedicated graphics card, CPU inference (P §1.6) | The baseline on CPU-only 16 GB machines; the engine on a MacBook Air M4 (16 GB), then a MacBook Pro M5 Pro (24 GB) | MLX needs Apple silicon and uses its integrated graphics processor, not a dedicated card; the Pro was adopted for speed, with the Air's results kept (E-17) |
| Qwen2.5, Llama 3.2, Phi-3 through Ollama; a BGE embedder (P §3.6) | The baseline as proposed; the engine on Qwen3 1.7B, 4B and 8B and Qwen3-Embedding through MLX | The engine must read and write the reader's cache in its own process; one embedder serves every contender (E-02) |
| Ranking by similarity, recency and importance (P §3.5.1) | The baseline defaults to similarity, gate and bridging; the engine chooses the closest moment's room | The composite lowered full-support recall on both multi-hop sets (F1; Section {sec:baseline-results}) |
| A fixed token budget (P §3.5.1) | Rooms capped at 512 tokens plus four moments re-read | Larger rooms knew fewer facts at every setting tried (E-18) |
| A pinned hosted reference model as the ceiling (P §3.6.3) | Kimi K3 for the baseline; Claude Haiku, Sonnet and Opus 5.5 as a yardstick for the engine | A cloud model with a one-million-token window sees the whole history early and only its end later, so it is reported beside the engine, not as a fixed ceiling |
| Public benchmarks only; "not an end-user application" (P §1.6) | The Long Haul, the Hugging Face suites, and a Mac chat app | The claim is about a memory that grows over months, which no public set tests; the final project also needs a usable release |

Parts of the design were planned but not built, because the remaining time went to the evaluation. No requirement above depends on them, and they are taken up as future work in Chapter 6: naps that run on their own while the Mac is charging; distilling what was learnt, checked by a quiz before it is kept; settling unsure facts at recall; reading several rooms together; and the native engine (notes rather than words) behind the pairing and the OpenAI-compatible endpoint.

## Chapter Summary {#design-summary}

This chapter specified CAMR in three stages, using structured, UML and storage views suited to an experimental AI artefact. It stated 32 functional, 16 non-functional, 8 data and 10 interface requirements, each with a source and a verification method and without invented thresholds, and traced them to the objectives. The analysis presented CAMR as a closed system on the Mac and described its actors, main use cases and evaluation workflow. The design described the baseline's paths over one SQLite file; the engine's memory of saved notes in rooms on the SSD, read one room at a time after a small core with the four closest moments re-read as words; its classes; the assistant that routes, researches, reads files, revises, files by topic and compares CAMR with RAG; the life cycle of rooms between RAM, the SSD and sleep under fixed budgets; the files of a memory; and the deployment on one Mac. The main changes from the proposal were justified from evidence. Chapter 5 reports how this design was implemented, tested and evaluated.
