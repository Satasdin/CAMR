# Chapter 3:  Methodology

## 3.1 Introduction

This chapter describes how the study was carried out. It states the research paradigm that guided the work, the development approach that was followed, the analysis of what the system had to do, the design of both the system and the experiments that evaluated it, the tools and techniques that were used, and the deliverables the study produced. Throughout the chapter, the guiding principle is that the measurement apparatus was built and validated before the system it measures, so that every subsequent design decision could be evaluated as a controlled experiment. Where the work departed from the proposal approved in June 2026, the chapter says so plainly.

## 3.2 Research Paradigm

The study adopted a pragmatist research philosophy, combining design science research with controlled experimentation. Design science research is appropriate because the study created and evaluated a novel artefact, the memory engine, and the discipline's guidelines require that such an artefact be evaluated rigorously against explicit measures of utility (Hevner et al., 2004). The study followed the design science research methodology of Peffers et al. (2007), proceeding through problem identification, definition of solution objectives, design and development, demonstration, evaluation, and communication. The evaluation took the form of controlled experiments organised as a research pipeline of four stages, described in the subsections that follow.

### 3.2.1 Data Acquisition

Evaluation data was acquired so that knowledge-bound and reasoning-bound performance could be separated. The knowledge-bound data came from three curated subjects that the on-device model cannot know well. The first was Kenyan data protection law: the Data Protection Act (2019) and its 2021 regulations. The second was software documentation published in 2026, after the on-device models were trained: the Model Context Protocol specification, the release notes of Ollama, and the release notes of Python 3.15. The third was a private software project, the source code and decision record of Burrow itself. The reasoning-bound data came from GSM8K, an established public benchmark of mathematical reasoning questions (Cobbe et al., 2021), downloaded from its official distribution.

This is a change from the proposal. The proposal named the public question-answering benchmarks PopQA (Mallen et al., 2023), HotpotQA (Yang et al., 2018), and 2WikiMultiHopQA (Ho et al., 2020) as the knowledge-bound data. They were replaced by the curated subjects because the memory of the engine as built is a personal vault of a person's own documents, and an encyclopaedia corpus does not represent that memory. The single-fact and multi-fact question types of those benchmarks were kept.

### 3.2.2 Data Preparation

The documents of the three subjects were placed in one vault as Markdown files, and the engine indexed the vault before any evaluation began. For each subject, twenty-five single-fact questions and fifteen multi-fact questions were written from the documents, each with an answer key and the passage that supports it. A script checked every key against the text of the vault. From GSM8K, fifty questions were drawn once from the test split with a fixed random seed. The same questions were reused across all conditions so that every comparison is paired. The vault was populated from the source documents only, never from the question-answer pairs themselves, so that the experiment measures the engine's ability to surface relevant knowledge rather than its ability to look up a planted answer. The three subjects shared one vault, so the documents of two subjects acted as distractors for the third, and retrieval had to discriminate, not merely fetch.

### 3.2.3 Experimental Conditions

Four main conditions were run on every evaluation question: a floor condition in which the on-device model answered alone, a treatment condition in which the on-device model answered with Burrow, a ceiling condition in which the large cloud reference model answered alone, and a fourth condition in which the cloud model answered with Burrow. A standard vector database pipeline built on Chroma served as the baseline. The full design of these conditions is given in section 3.5.2.

### 3.2.4 Measurement and Validation

Every query in every condition logged the model used, the engine configuration, the tokens supplied and generated, the wall-clock time, and the resulting answer, so that every experiment is reproducible from its logs. Answer quality was scored against the answer key, and the central quantity of the study, the fraction of the capability gap closed, was computed from the conditions as defined in section 3.5.2. Validity was protected by the paired design, an exact sign test on paired answers, a frozen copy of the engine, and the threat mitigations described in section 3.5.6.

## 3.3 Development Approach

The system was developed incrementally, in small working stages, each of which was evaluated before the next was begun. An incremental approach suited this study for two reasons. First, the central research instrument, the evaluation harness, had to exist before the engine, because every component of the engine was judged by the harness's measurements; building measurement first removed the largest project risk, which is discovering late that results cannot be produced. Second, the engine itself is designed as a chain of separable steps, and adding them one at a time turned development into the component-by-component study that the objectives require.

Development proceeded in five increments, shown in Figure 3.1. The first increment built the evaluation harness: the task loaders, the floor and ceiling model runners, the answer scorers, and the logging of tokens and time for every query, validated by producing a baseline gap measurement with no memory engine at all. The second increment added the simplest complete treatment: files indexed with embeddings, retrieval by search alone, and packing into a fixed budget, establishing the control condition against which the richer engine is compared. The third increment added the remaining components one at a time: the walk over links between files, the Decide step, the Fit step, the Check step, the Learn step, and the skills. The fourth increment profiled the complete engine on the target device, measuring the time and the tokens of every answer. The fifth increment, which the proposal did not plan, added the surfaces through which the engine is used: a native Mac application, a terminal chat, and a Model Context Protocol server. The graph-based retrieval layer that the proposal listed as an optional fifth increment was built inside the third increment as the walk over links.

The engine was first prototyped in Python under the working name CAMR and was rebuilt in Swift as Burrow after the Sprint II review of 5 November 2026.

!fig figures/related/fig3-1-incremental.png | Figure 3.1: Incremental development approach for the Burrow engine. | 6.2

## 3.4 System Analysis

The requirements for the engine were formulated by working backwards from the study objectives and the measurements the evaluation demands, so that every capability maps to something the experiments need. In functional terms, the engine had to index a vault of notes, documents, and code with their embeddings in an on-device database, decide whether an incoming question needs the vault, retrieve and rank candidate passages by word match and by meaning, follow the links between files, assemble the top-ranked excerpts into a token budget fitted to the local model, check the sources an answer cites, propose a compact note from a conversation and write it only with consent, and log the model, configuration, token counts, time, and answer for every query so that each experiment is reproducible. In non-functional terms, it had to run entirely on the target consumer laptop with no dedicated graphics card and only the large reference model reached through a cloud API, add no more than a small fraction of total answer time through retrieval, keep the index as a single local file with no server process, retain all data on the device and operate offline in every configuration except the cloud conditions, and run the full experimental pipeline from the command line.

## 3.5 System Design

This section describes the design of the memory engine and, with equal weight, the design of the experiments that evaluated it. The two are presented together because the engine's components are defined by the measurements that justify them.

### 3.5.1 Architectural Overview

The engine consists of three parts arranged around a frozen local language model. The first part is the vault, the memory itself: a folder of plain Markdown notes and documents, with linked code folders, kept in the person's own files. The second part is the index, which the engine can rebuild from the vault at any time. It is a single embedded relational database holding a full-text index, the embedding vector of every passage, and a table of the links between files, with a memory-mapped block of normalised vectors beside it for fast comparison. The third part is the engine, which takes five steps on every question. In the Decide step it judges whether the question needs the vault at all, and whether to search or to follow links between files. In the Fit step it uses a measurement of the hosted model, its reading speed and its size, taken once, to set the token budget: how much memory that model is shown. In the Answer step the frozen model answers from the packed excerpts. In the Check step every file and line the answer cites is checked against what the model was shown, and a wrong citation triggers one retry. In the Learn step, after a conversation, the engine proposes notes of what the person decided, each backed by the person's own words, and writes them only with consent.

These steps realise the three mechanisms of the proposal. The Learn step is the write policy. The Decide step and the retrieval behind it are the retrieval policy. The Fit step is the token budgeting mechanism. Retrieval merges a ranking by word match, computed with BM25 (Robertson & Zaragoza, 2009), and a ranking by meaning, computed as the cosine between embedding vectors, using reciprocal rank fusion (Cormack et al., 2009), and then walks the links between files. This replaces the weighted score of similarity, recency, and importance that the proposal took from Park et al. (2023). The engine also keeps a store of skills, short Markdown methods for kinds of task such as answering from documents, working a calculation, fixing a bug, or explaining code. The engine picks the skill that fits and hands it to the model with the question. The model's weights remain untouched in every configuration. The detailed component design is presented in Chapter 4.

### 3.5.2 Experimental Design

The central quantity of the study is the fraction of the capability gap closed, and the experiment was designed around measuring it cleanly. The same questions were put to every condition. The floor condition was the on-device model answering alone, with no memory. The ceiling condition was the large cloud reference model answering alone. The treatment condition was the on-device model answering with Burrow. A fourth condition gave the cloud model the same memory, prepared by Burrow, so that the engine could also be observed with a stronger model. Two further set-ups placed the treatment in context: the on-device model with plain search pasted into the prompt, which is the control of the second increment, and the on-device model with a standard vector database pipeline built on Chroma, which is the outside baseline. The Chroma pipeline cut the same vault into pieces, embedded them with the same embedding model, and was given the same limit on characters as plain search. Each on-device set-up was run with the main model and with the small model. For each task type, the gap closed was computed as shown in Equation 3.1, where S denotes the accuracy score of a condition on that task type.

!eq gap | Equation 3.1: Fraction of the capability gap closed.

A value of zero means the engine added nothing and a value of one means the on-device model with memory matched the large model. Where the cloud model was not ahead of the on-device model alone, the quantity is not defined and is reported as such. On the private project the cloud model alone cannot know the answers, so the gap for that subject is reported against the cloud model with the same memory. Alongside accuracy, every query in every condition logged the tokens supplied to the model, the tokens generated, and the wall-clock time, so that accuracy per token and accuracy per second can be reported, not just accuracy.

Two design guards were enforced throughout. The evaluation questions were held out of the corpus from which the vault was built, as described in section 3.2.2. The engine was frozen as one binary before the first scored run, its thresholds were set on separate development questions, and the plan of the evaluation was written down before any scored run.

### 3.5.3 Datasets and Task Types

The data introduced in section 3.2.1 was assigned to task types as follows. Each curated subject provided single-fact questions, whose answer is one fact in one stored passage, and multi-fact questions, whose answers require combining facts from more than one stored passage. Together these are the knowledge-bound tasks, the case where an on-device model fails most severely and where the gap is therefore widest and most visible (Mallen et al., 2023). GSM8K provided grade-school mathematical reasoning questions as the control task type, where the required ability is reasoning rather than recall and where memory was predicted to help little (Cobbe et al., 2021). A null result on the reasoning control was to be treated as a positive finding, since it would demonstrate that the engine does what it claims, supplies knowledge, and not what it does not claim.

Two earlier tests, carried out on the first version of the retrieval before the engine steps were added, are also reported. Retrieval alone was tested on 101 real bug fixes drawn from the repositories of SWE-bench (Jimenez et al., 2024), where the question is the text of the issue and the target is the files that the fix changed. Simulated developer agents were run on software projects held back from development, to observe whether memory of earlier decisions carried from one working session to the next.

### 3.5.4 Evaluation Metrics

Answer quality was scored as accuracy against an answer key. A knowledge-bound answer was marked right when it contained every required fact of its key, and a reasoning-bound answer was marked right when its final number equalled the key. This replaces the exact match and token-level F1 metrics of the public benchmarks named in the proposal. From these scores, the gap closed was computed per task type using Equation 3.1. Efficiency was reported as tokens read per query, tokens generated per query, the time spent before the model is called, and the seconds taken per answer, all measured on the target device. Paired comparisons between conditions were tested with an exact two-sided sign test, which replaces the bootstrap confidence intervals of the proposal because each answer is simply right or wrong. Where two configurations achieve similar accuracy, the one that does so with fewer tokens and less time is judged superior, since on a device every token costs time.

### 3.5.5 Ablation Procedure

Each component of the engine was evaluated by comparing a configuration that has it with one that does not, holding everything else fixed. The control was the simplest complete treatment: plain search and a fixed budget. Against this control, the complete engine measures the joint effect of the Decide, Fit, and Check steps and the skills. The engine was then run on the main model without its skills, and again without its Check step, to measure each of those alone. The effect of the token budget was observed through the Fit step, which sets a different budget for each of the two on-device models. Each comparison is reported as a row stating the change in gap closed, the change in tokens per query, and the change in time, so that the value of every design decision is individually visible and the final engine is justified component by component rather than as a whole. [PENDING: confirm whether a sweep of fixed token budgets was run for research question iv]

### 3.5.6 Threats to Validity

Six threats were controlled. Answer leakage was prevented by the holdout guard (sections 3.2.2 and 3.5.2); prompt sensitivity by one fixed instruction per condition, with every model run at a temperature of zero; sampling error by paired samples and the exact sign test; tuning on the test by freezing the engine and setting its thresholds on separate development questions; ceiling instability by pinning and logging a fixed reference-model version; and scorer error by fixed marking rules that are themselves covered by automated tests. Two threats remain and are stated with the results: the questions on the curated subjects were written by a language model and not by people, and all timing comes from one machine with one run per question.

## 3.6 Tools and Techniques

This section describes the tools that were used to build the engine and the harness, and the role each played.

### 3.6.1 Swift

The engine, the command-line tool, the terminal chat, the Model Context Protocol server, and the Mac application were implemented in Swift, the native language of the target platform, so that the engine runs as one compiled program with no interpreter on the device. The proposal named Python for the engine; the change followed the Sprint II review.

### 3.6.2 SQLite with Full-Text Search

The index is one SQLite database, a serverless local file, which reflects the realities of on-device deployment and requires no running database server. The full-text index uses the FTS5 extension of SQLite (SQLite, 2026). Vectors are stored in the same database and compared through a memory-mapped block, in place of the vector search extension named in the proposal.

### 3.6.3 Ollama and Local Models

Local models were served through Ollama, which manages quantised open-weight models on consumer hardware (Ollama, 2026). The on-device models were Gemma 4 12B (Gemma Team, 2026) as the main model and Qwen3.5 4B (Qwen Team, 2026) as the small model. They replace the Qwen2.5, Llama 3.2, and Phi-3 models named in the proposal with open-weight models released in 2026.

### 3.6.4 Hosted Inference API

The large reference model, Claude, was accessed through the hosted inference API of Anthropic and pinned to a single version for the duration of the study, so that the ceiling anchor remained stable across all experiments. [PENDING: pinned model identifier]

### 3.6.5 Embedding Model

Embeddings were produced on the device by the Qwen3 Embedding model at 0.6 billion parameters, served through Ollama (Zhang et al., 2025). It replaces the BGE model named in the proposal (Xiao et al., 2024).

### 3.6.6 Chroma

The baseline pipeline was built on Chroma, an open-source vector database (Chroma, 2026), running locally with the same embedding model as the engine.

### 3.6.7 LangChain

An adapter exposes Burrow as a retriever for LangChain, a widely used framework for building applications around language models (LangChain, 2026), to show that the engine can take the place of a vector database in an existing pipeline.

### 3.6.8 Python

The evaluation harness was implemented in Python. It runs every condition, scores the answers, and writes the tables from the logged results.

### 3.6.9 Auxiliary Tools

Version control used Git. All experiment results were written as structured records so that every figure and table in this document can be regenerated from the logs. The target machine for all development and all device measurements was an Apple MacBook Pro with an M5 Pro chip, 24 gigabytes of shared memory, and no dedicated graphics card.

## 3.7 Deliverables

The study produced the following deliverables, each described in its own subsection.

### 3.7.1 The Burrow Memory Engine

A documented Swift package implementing the vault, the index, and the engine steps described in section 3.5.1, runnable entirely on the target consumer laptop, with a command-line tool.

### 3.7.2 The Application, Terminal Chat, and Model Context Protocol Server

A native Mac application and a terminal chat through which a person uses the engine, and a Model Context Protocol server through which other tools and models use the same memory. These were not in the proposal and were added after the Sprint II review.

### 3.7.3 The Evaluation Harness

The task loaders, condition runners, scorers, and logging needed to reproduce every experiment in the study from the command line.

### 3.7.4 Experimental Results

The measured gap closed per task type, the comparison with the baseline, the ablation rows, and the device cost profile of tokens and time, together with the complete regenerable logs that support them.

### 3.7.5 System Documentation

The final project document reporting the design, the experiments, and the findings, including the prompt templates, configuration files, and instructions sufficient for an independent reader to reproduce the results.
