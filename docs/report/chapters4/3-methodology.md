# Chapter 3:  Methodology

## 3.1 Introduction

This chapter describes how the study was carried out. It states the research paradigm that guided the work, the development approach that was followed, the analysis of what the system must do, the design of both the system and the experiments that evaluated it, the tools and techniques that were used, and the deliverables the study produced. The system was analysed and designed with Object-Oriented Analysis and Design (OOAD). Throughout the chapter, the guiding principle is that every claim about the engine was tested as a controlled experiment.

## 3.2 Research Paradigm

The study adopted a pragmatist research philosophy, combining design science research with controlled experimentation. Design science research is appropriate because the study created and evaluated a new artefact, the memory engine, and the discipline's guidelines require that such an artefact be evaluated rigorously against explicit measures of utility (Hevner et al., 2004). The study followed the design science research methodology of Peffers et al. (2007), proceeding through problem identification, definition of solution objectives, design and development, demonstration, evaluation, and communication. The evaluation took the form of controlled experiments organised as a research pipeline of four stages, described in the subsections that follow.

### 3.2.1 Data Acquisition

Two kinds of data were acquired, so that knowledge-bound and reasoning-bound performance could be separated. The knowledge data was a curated vault on three subjects that an on-device model cannot know well: Kenyan data protection law, taken from the Data Protection Act and its three sets of 2021 regulations (Data Protection Act, 2019); software documentation dated 2026, namely the release notes of SQLite, Python 3.15, Ollama, and the Model Context Protocol; and a private software project, the source code and decision record of Burrow itself at an earlier version. The reasoning data was 50 problems from GSM8K, a public benchmark of grade-school mathematics problems (Cobbe et al., 2021). All of the documents are public or belong to the author, and none contains personal data about any person. Each record is a question, its answer key, and, for a knowledge question, the passage that supports the key, as Table 3.1 shows.

!tab Table 3.1: Two records of the evaluation data
!widths 1.0,2.9,2.4
| Kind | Question | Answer key |
| Knowledge, one fact | Under Kenya's Data Protection Act, 2019, within how many hours of becoming aware of a personal data breach that poses a real risk of harm must a data controller notify the Data Commissioner? | seventy-two or 72 |
| Knowledge, several facts | Across SQLite 3.53.0 and 3.54.0 (both released in 2026), which three new options were added to the sqlite3_limit() interface? | SQLITE_LIMIT_PARSER_DEPTH; SQLITE_LIMIT_SCHEMA; SQLITE_LIMIT_TRIGGER_STEPS |

### 3.2.2 Data Preparation

The documents of the three subjects were converted to Markdown files and placed in one vault, so that the documents of two subjects stood as distractors for the third. The engine then indexed the vault before any evaluation began. For each subject, 25 single-fact questions and 15 multi-fact questions were written from the documents by Claude Code agents, and a script checked every key against the text of the vault and rejected any key that appeared in its own question. The reasoning problems were drawn once from the GSM8K test split with a fixed random seed. The vault was built from the source documents only, never from the questions or their keys, so that the experiment measured the engine's ability to surface relevant knowledge rather than its ability to look up a planted answer. The same questions were reused in every set-up, so that every comparison was paired.

### 3.2.3 Experimental Conditions

Six set-ups were run on every evaluation question. The floor was the on-device model alone, the ceiling was the cloud model alone, and the treatment was the on-device model with the memory engine. No model was trained or fine-tuned; the weights stayed frozen in every set-up, because the engine works beside the model and does not change it. The full design of these conditions is given in Section 3.5.2.

### 3.2.4 Measurement and Validation

Every question in every set-up logged the model used, the tokens read and written, the seconds spent before the model was called, the seconds the model took, and the resulting answer, so that every experiment could be examined from its logs. The central quantity of the study, the fraction of the capability gap closed, was computed from the set-ups as defined in Section 3.5.2. Validity was protected by the paired design, an evaluation plan written before any scored run, a program frozen before the first scored run, and the measures described in Section 3.5.6.

## 3.3 Development Approach

The system was developed by incremental prototyping, in small working stages, each of which was checked before the next was begun. Iterative and incremental development grows a system in small steps in which the result of each step informs the next (Larman & Basili, 2003), and design science asks for the same cycle of building and evaluating (Hevner et al., 2004). This approach suited the study for two reasons. First, the requirements changed: the Sprint II review of 5 November 2026 asked for something a person can see and use, and an incremental plan could take that in without losing the work already done. Second, the engine is a chain of separable steps, so its parts could be built in turn and switched off when it was evaluated. The system was analysed and designed with OOAD, because the memory is naturally a set of objects that hold their own data and behaviour, and Chapter 4 therefore presents use case, sequence, activity, and class diagrams drawn in the Unified Modeling Language.

Development proceeded in the five increments shown in Figure 3.1. The first increment built a memory engine and an evaluation harness in Python under the working name CAMR, from the approved proposal, and ended at the Sprint II review. The second increment rebuilt the memory in Swift as Burrow, with a vault of plain Markdown files, a rebuildable SQLite index, retrieval by words and by meaning, and a walk over the links between files. The third increment added the surfaces through which a person and other tools use the memory: a native desktop application, a terminal chat, and a Model Context Protocol server. The fourth increment froze the retrieval and tested it on 101 real bug fixes from public repositories and on three held-back synthetic projects worked by simulated developer agents; memory did not measurably help the small model write working code, which showed that finding the right text was not enough. The fifth increment built the engine around the model, namely the Decide, Fit, Check, and Learn steps and the skills, wrote the evaluation harness of Section 3.5, froze the program, and ran the evaluation.

!fig figures/related/fig3-1-incremental.png | Figure 3.1: Incremental development approach for the Burrow engine, drawn by the author. | 6.2

## 3.4 System Analysis

The requirements were worked backwards from the study objectives, the measurements the evaluation needs, and the Sprint II review, so that each capability maps to an experiment or to the person using the system. Following OOAD, they were analysed with a use case diagram, sequence diagrams, an activity diagram and a class diagram, and stated as functional, non-functional, data and interface requirements with identifiers; Sections 4.2 and 4.3 present them.

## 3.5 System Design

This section states how the engine and the experiments that evaluated it were designed.

### 3.5.1 Architectural Overview

The engine was designed as a chain of steps around a frozen local model, with the memory kept as plain files beside one embedded index that can be rebuilt from them. The design was captured in a system architecture diagram, a diagram of the engine's steps, a logical database schema, wireframes and a deployment diagram, which Section 4.4 presents.

### 3.5.2 Experimental Design

The central quantity of the study is the fraction of the capability gap closed, and the experiment was designed around measuring it cleanly. Six set-ups were run on every question: the on-device model alone, which is the floor; the on-device model with plain retrieval; the on-device model with a vector database baseline built on Chroma; the on-device model with the engine, which is the treatment; the cloud model alone, which is the ceiling; and the cloud model with the memory prepared by the engine. The first four were run with both on-device models, at a temperature of zero. Plain retrieval and the Chroma baseline used the same vault, the same embedding model, and the same limit of 12,000 characters. The engine showed Gemma 4 12B up to 17,417 characters, the budget its fit produced, and Qwen3.5 4B up to 12,000, and the cloud model with the engine was shown up to 24,000. For each task type, the gap closed was computed as shown in Equation 3.1, where S denotes the accuracy of a set-up on that task type. Two ceilings were reported: the cloud model given the same vault, which compares like with like on material the cloud model could not have seen in training, and the cloud model alone.

!eq gap | Equation 3.1: Fraction of the capability gap closed

A value of zero means the engine added nothing, and a value of one means the on-device model with the engine matched the cloud model. Where the cloud model was not ahead of the on-device model alone, the measure is not defined. A rule added after the evaluation plan was written leaves the fraction out of Table 5.6 when the ceiling is less than ten percentage points above the floor, because one answer then moves it widely.

### 3.5.3 Datasets and Task Types

The 120 knowledge questions, 40 on each of the three subjects, were the knowledge-bound task type. Each subject held 25 single-fact questions and 15 multi-fact questions, and a multi-fact question needs two passages from two different files. These questions are the case where a small model fails most severely, because it cannot have memorised the material. The 50 GSM8K problems were the reasoning-bound control, where the required ability is reasoning rather than recall and where memory was predicted to help little (Cobbe et al., 2021). The question for this control was whether the engine would leave the vault out and protect the answer.

### 3.5.4 Evaluation Metrics

A knowledge answer was right when it contained every required fact of its key, and a reasoning answer was right when its last number equalled the key. Accuracy was the share of right answers in a set-up, and the gap closed was computed from it per task type using Equation 3.1. Retrieval was also judged apart from answering, by recording whether every file that holds the answer was among the excerpts shown. Efficiency was reported as the tokens read, the tokens written, the seconds spent before the model was called, and the seconds the model took, all measured on the target device. Paired differences between set-ups were tested with an exact two-sided sign test, because each answer is simply right or wrong.

### 3.5.5 Ablation Procedure

Parts of the engine were evaluated by switching them off and measuring the change on the same questions, holding everything else fixed. The full engine on the main model was the reference. One run removed the skills and another removed the citation check, and each was reported beside the full engine. The token budget was varied separately on the 120 knowledge questions, with the amount shown fixed at 2,000, 4,000, 8,000, and 32,000 characters beside the fitted 17,417. This sweep was added after the evaluation plan was written, in order to answer the fifth specific objective, so no criterion for it was set in advance. Decide and Fit were not switched off on their own.

### 3.5.6 Threats to Validity

Six threats were addressed. Answer leakage was prevented by building the vault from the source documents only (Section 3.2.2). Prompt sensitivity was limited by one fixed prompt for each set-up. Sampling error was addressed by paired questions and an exact sign test. Timing noise was addressed by reporting medians on one machine, although each question was run once. Ceiling instability was addressed by pinning and logging one version of the cloud model. Tuning bias was addressed by setting the thresholds of the engine on separate development questions, although several concern the same subjects as scored questions, while the scored questions were not read during tuning and played the part of a held-out test set.

## 3.6 Tools and Techniques

This section describes the tools that were used to build the engine and the harness, and the role each played. Their exact versions are given in Section 5.2.2.

### 3.6.1 Swift

The engine, the command-line tool, the terminal chat, the protocol server, and the desktop application were written in Swift, the native language of the target platform, so that the engine runs as one compiled program with no interpreter.

### 3.6.2 SQLite with FTS5

The index is SQLite, one database file with no server process. The word index uses the FTS5 full-text extension (SQLite, 2026), and the embedding vectors are stored in the same database with a memory-mapped copy beside it for speed.

### 3.6.3 Ollama and Local Models

Local models were served through Ollama, which runs quantised open-weight models on consumer hardware (Ollama, 2026). The on-device models were Gemma 4 12B and Qwen3.5 4B (Gemma Team, 2026; Qwen Team, 2026).

### 3.6.4 Hosted Inference API

The cloud reference model, Claude (Anthropic, 2026c), was reached through its hosted API and pinned to a single version for the whole study, so that the ceiling remained stable across all runs.

### 3.6.5 Embedding Model

Embedding vectors were produced on the laptop by Qwen3 Embedding 0.6B (Y. Zhang et al., 2025). The engine and the baselines used the same model.

### 3.6.6 Chroma and LangChain

Chroma, an open-source vector database (Chroma, 2026), was run locally to build the baseline of Section 3.5.2. LangChain, a framework for applications around language models (LangChain, 2026), was supported through an adapter that exposes Burrow as a retriever.

### 3.6.7 Model Context Protocol

The Model Context Protocol, an open standard between AI applications and data sources (Model Context Protocol, 2026), was used so that outside models and tools can reach the same memory.

### 3.6.8 Auxiliary Tools

The evaluation harness, the scripts that check the answer keys, and the charts were written in Python. Claude Code wrote the knowledge questions under the checks of Section 3.2.2. Version control used Git and GitHub, and the state of the code at each evaluation was marked with a tag, so that a result can be traced to the code that produced it.

## 3.7 Deliverables

The study produced the following deliverables, each described in its own subsection.

### 3.7.1 The Burrow Memory Engine

A Swift package that implements the vault, the index, and the engine designed in Chapter 4, with a command-line tool named burrow, running entirely on the target consumer laptop.

### 3.7.2 The Desktop Application, Terminal Chat, and Protocol Server

A native desktop application in which a person writes notes, follows their links, and asks questions of the vault, a terminal chat, and a Model Context Protocol server that gives outside models and tools the same memory.

### 3.7.3 The Evaluation Harness

The question sets, set-up runners, scorers, and logging needed to repeat every experiment in the study from the command line.

### 3.7.4 Experimental Results

The measured gap closed per task type, the ablation and budget results, and the cost of each answer in tokens and seconds, together with the logs that support them.

### 3.7.5 System Documentation

This report, including the design, the experiments, and the findings, with the instructions, configuration files, and prompt templates needed to reproduce the results.
