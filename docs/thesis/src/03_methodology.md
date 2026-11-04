# Methodology {#method}

## Introduction

This chapter describes how the study was carried out. It states the research paradigm that guided the work, the development approach that was followed, the analysis of what the system had to do, the design of both the system and the experiments that evaluated it, the tools and techniques that were used, and the deliverables the study produced. Throughout, the guiding principle was that the measurement apparatus was built and validated before the system it measures, so that every later design decision could be judged as a controlled experiment. Chapter 4 gives the full requirements and design, and Chapter 5 the implementation and results.

## Research Paradigm

The study adopted a pragmatist research philosophy, combining design science research with controlled experimentation. Design science research is appropriate because the study created and evaluated a novel artefact, the memory engine, and the discipline's guidelines require that such an artefact be evaluated rigorously against explicit measures of utility (Hevner et al., 2004). The study followed the design science research methodology of Peffers et al. (2007), proceeding through problem identification, definition of solution objectives, design and development, demonstration, evaluation and communication. The evaluation took the form of controlled experiments organised as a research pipeline of four stages, described in the subsections that follow.

### Data Acquisition {#data-acq}

Evaluation data came from three sources, chosen so that knowledge-bound and reasoning-bound performance could be separated.

1. **Public question-answering benchmarks** for the baseline: PopQA for single-hop long-tail facts (Mallen et al., 2023), HotpotQA and 2WikiMultiHopQA for multi-hop facts (Z. Yang et al., 2018; Ho et al., 2020) and GSM8K for mathematical reasoning (Cobbe et al., 2021), with the document collections that accompany the factual benchmarks.
2. **A scripted long project, the Long Haul,** written for this study because no public set tests a memory that grows over months. It is generated from a seed, so the same seed always gives the same script, and every planted fact has one answer a rule can check (Section {sec:longhaul-data}).
3. **Public suites from the Hugging Face Hub** for the engine's comparison with the cloud yardstick: MATH-500 (Hendrycks et al., 2021; Lightman et al., 2024), AIME 2025 and 2026 (Balunović et al., 2025), HARP correction pairs (Yue et al., 2024) and BABILong (Kuratov et al., 2024).

All public datasets are released for research use and were downloaded from their official distributions. Earlier development of the engine also used three scripted twelve-week lives of invented people (Section {sec:rooms-results}).

### Data Preparation {#data-prep}

From each public benchmark, a fixed random sample of questions was drawn once, with a fixed seed, and reused across all conditions so that every comparison is paired. The baseline's memory was populated from the supporting document collections only, never from the question–answer pairs, so the experiment measured the engine's ability to surface relevant knowledge rather than to look up a planted answer. Distractor documents were included, so that retrieval had to discriminate, not merely fetch.

The Long Haul was prepared the same way. It was cut at fixed sizes (64,000, 256,000, 1 million and 2 million tokens, and after an extension 3 and 4 million). At each cut a checkpoint draws a stratified sample of the questions that can be asked there, ten from each family with a fixed seed, so every contender answers exactly the same 216 questions (E-30; decisions are cited by their number in the project's decision log, summarised in Appendix B). Questions are asked only after the history has been told, and asking never teaches: the engine's questions are read-only, so a question asked early does not help the same question asked later (E-31).

### Experimental Conditions {#conditions}

The baseline ran three conditions on every question: a floor, in which the small local model answered alone; a ceiling, in which the large cloud model answered alone; and a treatment, in which the small model answered with the memory engine. The engine's evaluation kept the same logic but named the conditions by what each contender can see (Table {tab:conditions}): the model alone with the newest part of the history that fits its window ("bare"), the same model with the engine, and the cloud model alone with the newest part that fits its one-million-token window. Every contender read the same instructions, so that only what each one could see differed (E-32).

### Measurement and Validation {#measurement}

Every answer in every condition was logged with the model, the engine's settings, the tokens read and written, the time to the first word, the total time, the retrieval time of each step, where the memory came from (RAM, SSD or words) and the RAM and disk in use. Answers were graded by rule, so the same answer always gets the same verdict and anyone can grade again. Each run wrote a dated record naming the machine, how busy it was and a fingerprint of the code that made it. Validity was protected by the paired design, by fixed seeds, by one measuring job at a time on the graphics processor (E-35), and by the threat mitigations in Section {sec:threats}.

## Development Approach {#dev-approach}

The system was developed incrementally, in small working stages, each evaluated before the next began. An incremental approach suited the study for two reasons. First, the central research instrument, the evaluation harness, had to exist before the engine, because every component of the engine was judged by its measurements; building measurement first removed the largest project risk, which is discovering late that results cannot be produced. Second, the engine was designed as a chain of separable components, so adding them one at a time turned development into the comparisons that the fifth objective required.

Development ran in five increments.

1. **The baseline (CAMR v1).** The harness for the public benchmarks was built first and validated by a baseline gap measurement with no memory; then the text-note engine was added one component at a time (similarity retrieval and a token budget, then gating, entity bridging, verified answering and learning by lookup), each producing a measured row. Its results are summarised in Section {sec:baseline-results}.
2. **Step 0, the ruler.** Before the new engine existed, three scripted lives, their quiz and the baselines that would judge it were built and measured on the MacBook Air (E-01 to E-13).
3. **Step 1, rooms and notes.** The engine's first build stored the model's keys and values in rooms on the SSD; the room design was chosen on development lives, and pass marks were written before the held-out lives were run (E-14 to E-20).
4. **Step 2, the event log.** Each answer's attention over the moments on the desk was recorded so that an answer could be replayed and inspected (E-21).
5. **The final engine and its proof.** The core, the tiers and sleep, the vault, reach, metrics and the Ollama pairing were added, and the engine was measured on the Long Haul against the Claude yardstick (E-29 to E-43).

## System Analysis

This section analyses what the system had to do. The analysis studied the requirements that the research questions impose, since in this study the experiment itself is a primary stakeholder: every requirement traces to a measurement the study had to make. Users of the application are the second stakeholder. Chapter 4 lists every requirement with its source and verification method.

### Functional Requirements

The system had to keep what it is told as stored memory, with the date and source of each item; store memory durably on the device; find, for an incoming question, the memory it needs; assemble that memory within a set budget and give it, with the question, to a frozen local model; let the user turn memory off and choose whose memory a question reads; and log, for every answered question, the model, the engine's settings, the tokens supplied and generated, the time of each step and the answer, so that every experiment can be reproduced from its records. The evaluation harness had to generate or load each test set deterministically, run each contender on identical questions, grade each answer by rule and write a record after every checkpoint.

### Non-Functional Requirements

The system had to run entirely on the target laptop, with the sole exception of the cloud reference models, which are reached through an API and are not part of the engine. Finding memory had to add only a small fraction of the answer's time, and the time to the first word and the RAM in use had not to grow as the memory grew. All stored data had to remain on the device, and the engine had to work without a network once its models were downloaded. Spending on the cloud reference had to be capped and logged call by call. The whole experimental pipeline had to be runnable from documented commands, so that results can be regenerated and verified.

## System Design

This section describes the design of the memory engine and, with equal weight, the design of the experiments that evaluated it.

### Architectural Overview

The engine has three parts arranged around a frozen local language model. The write path runs when the user tells it something: the moment is embedded, placed in the room of its closest earlier moment if that moment is close enough and the room has space, and read once by the model with the room's earlier moments in view; the keys and values the model writes while reading are appended to the room's file on the SSD. The store is a folder of files: one file of notes per room, an index of every moment's words, day and place, a matrix of embeddings, and a vault of plain-text notes. The read path runs when a question arrives: the question is embedded, the moment closest to it is found, and that moment's room is laid in front of the model already read, after a small core of standing facts; the model then reads the four closest moments as words, the date and the question, and answers. Rooms used recently stay in RAM; others are read from the SSD in one burst; when the room files outgrow their disk budget, the weakest rooms go to sleep and are read as words. The model's weights and inference code are never changed. The baseline's architecture, a single SQLite file with a ranked, gated and bridged read path, is described in Chapter 4 for comparison.

### Experimental Design

The central quantity of the baseline's evaluation was the fraction of the capability gap closed, computed for each task type by Equation {eq:gap}, where S is the accuracy score of a condition on that task type.

$$\text{gap closed} = \frac{S_{\text{treatment}} - S_{\text{floor}}}{S_{\text{ceiling}} - S_{\text{floor}}}$$ {#gap} [Fraction of the capability gap closed]
A value of zero means the engine added nothing and a value of one means the small model with memory matched the large model. The engine's evaluation reports right answers out of the questions asked at each size of history, for each contender, because the ceiling itself changes with the size of the history: a cloud model that sees the whole history at 256,000 tokens sees only its last part at 2 million. Table {tab:conditions} summarises the conditions.

Table: {#conditions} Experimental conditions

| Condition | Model | Memory | Purpose |
|---|---|---|---|
| Floor (baseline) or bare (engine) | Small local model (0.5–3B for the baseline; Qwen3 1.7B, 4B, 8B for the engine) | None: the newest part of the history that fits its window | Lower anchor |
| Ceiling (baseline) or yardstick (engine) | Kimi K3 (baseline); Claude Haiku, Sonnet and Opus 5.5 (engine) | None: the newest part that fits its window | Upper anchor; the yardstick is not a contender with memory |
| Treatment | The same small model as the floor | CAMR v1 (baseline) or CAMR (engine), settings varied per experiment | Measures what each configuration adds |
| Memory as words | Qwen 27B; Qwen3 1.7B through Ollama | The engine's memory, chosen the same way, pasted in as text | Separates what the memory knows from how it is delivered |

One design guard was enforced throughout: the questions were held out of what built the memory, so the experiment measured the engine's ability to surface relevant knowledge rather than to look up a planted answer. In the Long Haul a probe is planted early and asked late, and its right answer is resolved for the point at which it is asked.

### Datasets and Task Types

The datasets were assigned to task types as in Table {tab:datasets}. A null result on a reasoning task was treated as a positive finding, since it would show that the engine does what it claims, supplying knowledge, and not what it does not claim.

Table: {#datasets} Evaluation datasets and the task type each represents

| Dataset | Task type | Why it was included |
|---|---|---|
| PopQA (Mallen et al., 2023) | Knowledge-bound, single hop | Long-tail facts where small models fail severely (baseline) |
| HotpotQA (Z. Yang et al., 2018); 2WikiMultiHopQA (Ho et al., 2020) | Knowledge-bound, multi-hop | Answers combine facts across stored passages (baseline) |
| GSM8K (Cobbe et al., 2021) | Reasoning-bound (control) | Memory is predicted to help little (baseline) |
| The Long Haul (this study) | Both: facts, changed facts, look-alikes, two hops, corrected maths, code, a page, things never said | A memory that grows past every window; each family isolates one way of failing |
| BABILong (Kuratov et al., 2024) | Knowledge-bound, long context | Facts hidden in book text from 4,000 to 1 million tokens |
| HARP correction pairs (Yue et al., 2024) | Reasoning with a worked correction in memory | Whether a remembered worked solution carries to a new problem |
| MATH-500 (Lightman et al., 2024); AIME (Balunović et al., 2025) | Reasoning-bound, no memory | What each model can do on its own |

### Evaluation Metrics

Answer quality was scored with each benchmark's own rule: exact match and token-level F1 for the baseline's question-answering sets, the final answer for the mathematics sets, and, for the Long Haul, five verdicts given by rule (Table {tab:verdicts}). An answer about something never told is right only if it declines; a guess is counted as a false memory, separately from facts known, so that declining cannot raise a score. Efficiency was reported as the time to the first word, the total time, the retrieval time of each step, the tokens read, the peak RAM, the disk taken by the memory and, for the cloud models, the dollars spent at list price. Medians and the 90th percentile are reported, since a few long answers would distort a mean.

### Comparison Procedure

Each component of the engine was evaluated by changing it alone and measuring the result, holding everything else fixed. For the baseline the components were the write policy, recency and importance in the ranking, gating, entity bridging and the token budget. For the engine they were how notes are written and laid out (one moment at a time or a room at a time; one room or three), the size of a room and the number of moments re-read, the instructions the model reads, memory as notes against the same memory as words, the reach (session, project, global, project with global) and the cap on the graphics buffer cache. Each comparison is reported as a row stating the change in right answers and the change in time and memory.

### Threats to Validity {#threats}

The study guarded against the following threats. Answer leakage was prevented by building memory only from what the history tells, never from the questions. Prompt sensitivity was reduced by giving every contender the same instructions, pinned byte for byte by a test (E-32); the one exception, the 1.7B model's own wording, is reported both ways and was not chosen after seeing results on the test questions (E-37). Sampling error was addressed by paired comparisons on identical questions; the Long Haul's samples are small (34 to 73 questions per checkpoint), so differences of one or two answers are read as level. Timing noise was reduced by running one measuring job at a time, recording the machine's load with every record, and reporting medians. Instability of the cloud reference was handled by pinning model identifiers and recording the model that answered each request; no fallback model was ever used. Scorer error in grading by rule was checked by keeping every raw answer in the records so that any verdict can be checked by hand.

## Tools and Techniques

This section describes the tools that were used to build the engine and the harness, and the role each played.

### Python

The engine, the harness and the analysis were implemented in Python 3.12, the standard language of the research ecosystem the study draws on, with NumPy for vectors and the scientific Python stack for analysis and figures.

### MLX and Local Models

The engine runs its models through MLX on the Apple-silicon graphics processor (Hannun et al., 2023), because it must read and write the model's key–value cache inside its own process. The models were 4-bit Qwen3 1.7B, Qwen3 4B Instruct 2507 and Qwen3 8B (A. Yang et al., 2025), with Qwen 27B (`Qwen3.8-27B-4bit`) as the larger local comparison. The baseline served Qwen2.5, Llama 3.2 and Phi models through Ollama, which was also used for the engine's pairing test.

### Hosted Inference APIs

The cloud yardstick was Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5, reached through the Anthropic API with pinned model identifiers, streaming, and a ledger that logs every call's tokens and cost against a hard cap of $60 for a night of runs. The baseline's ceiling was Kimi K3 through the Moonshot API.

### Embedding Model

Moments are embedded by Qwen3-Embedding-0.6B (Zhang et al., 2025), run through MLX, which serves every contender so that differences between contenders are differences between memories (E-02). The baseline used the compact BGE embedder (Xiao et al., 2024).

### Storage on the Device

The baseline stored notes, vectors and logs in one SQLite file with a vector-search extension, as proposed. The engine instead stores one append-only file per room on the SSD, read and written with the operating system's file cache bypassed so that every read is a real SSD read, beside a JSON index, a NumPy embedding matrix and a folder of Markdown notes. Chapter 4 (Table {tab:changes}) gives the reason for the change.

### Application and Auxiliary Tools

The application's front end is a native macOS application written in SwiftUI, which starts the engine as a local process and talks to it over the loopback address. Version control used Git and GitHub, with the tests that need no MLX run by GitHub Actions on every push; pytest ran the test suite; a headless Chromium checked generated web pages. All results were written as structured JSON records, so every figure and table in this report can be regenerated from them.

## Deliverables

The study produced the following deliverables.

### The CAMR Memory Engine

A documented, installable Python package implementing the write path, the store, the read path, the three layers, reach and metrics described in Chapter 4, runnable entirely on an Apple-silicon Mac, with a pairing that gives Ollama memory as words.

### The Evaluation Harness

The Long Haul generator and grader, the runners for the engine, the bare models, Ollama and the Claude yardstick, the Hugging Face suites, and the baseline's benchmark pipeline, each reproducible from documented commands.

### Experimental Results

The measured results of the engine and the baseline, with the dated records that support every number.

### The Application and System Documentation

The native Mac application with its Chat and Code parts, the user guide, the decision log and this report, including the instructions sufficient for an independent reader to reproduce the results (Appendix A).

## Ethical Considerations {#ethics}

The study involved no human participants and no personal data. The baseline used established public benchmarks released for research use and an invented company. The engine was evaluated on scripted histories of invented people and an invented business, with Kenyan names and places; the only text sent to a cloud service was this scripted material, sent to the Claude yardstick under the provider's terms. All local models are open-weight models run on the Mac. Results are reported as they came out, including negative results and requirements that were not met. Cloud spending was metered call by call and capped. No user study was run, so no ethics approval was required; one would be needed before any study with real users (Chapter 6).
