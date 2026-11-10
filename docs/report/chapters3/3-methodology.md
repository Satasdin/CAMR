# Chapter 3:  Methodology

## 3.1 Introduction

This chapter describes how the study was carried out. It states the research paradigm and the four stages of the experiment. It then gives the development methodology and the reason it was chosen. The analysis and design followed Object-Oriented Analysis and Design, and the chapter names each diagram that Chapter 4 presents. It closes with the deliverables of the study and the tools that were used.

## 3.2 Research Paradigm

The study adopted an experimental research paradigm within a Design Science Research frame. Design science applies because the study built a new artefact, the Burrow memory engine, and an artefact of this kind must be evaluated against stated measures of usefulness (Hevner et al., 2004). The work followed the stages of Peffers et al. (2007): identify the problem, define the objectives, design and develop, demonstrate, evaluate, and communicate. The evaluation was a controlled experiment. The same questions were put to an on-device model with and without the engine, and to a large cloud model, and the answers were scored against keys. The four subsections below describe the data, its processing, the treatment of the models, and the testing.

### 3.2.1 Data Acquisition

Two kinds of data were acquired, so that questions bound by knowledge could be separated from questions bound by reasoning.

The knowledge data was a curated vault on three subjects that an on-device model cannot know well. The first subject was Kenyan data protection law: the Data Protection Act (2019) and its 2021 regulations, taken from Kenya Law. The second was software documentation dated 2026, published after the on-device models were trained: the Model Context Protocol specification, the release notes of Ollama, and the release notes of Python 3.15. The third was a private software project: the source code and the decision record of Burrow itself.

The reasoning data was 50 problems from GSM8K, a public benchmark of grade-school mathematics problems (Cobbe et al., 2021). The problems were drawn once from the test split with a fixed random seed.

### 3.2.2 Data Processing

The documents of the three subjects were converted to Markdown files and placed in one vault. The engine then indexed the vault. Each file was cut into pieces. Each piece was entered in a word index and given an embedding vector, and the links between files were recorded. The three subjects shared one vault, so the documents of two subjects stood as distractors for the third.

For each subject, 25 single-fact questions and 15 multi-fact questions were written from the documents. Each question carried an answer key and the passage that supports it. A script checked every key against the text of the vault. The vault was built from the source documents only and never from the questions or their keys. The same questions were used in every set-up, so every comparison was paired.

### 3.2.3 Model Training

No model was trained or fine-tuned in this study. The on-device models and the cloud model were used exactly as their publishers released them, and their weights stayed frozen in every set-up. This is the premise of the study: the engine works beside the model and does not change it.

What was set in place of training were the thresholds of the engine. These are the closeness below which the vault is left out of an answer, and the closeness at which a skill is matched to a question. They were set on development questions written for that purpose: 11 questions for the vault threshold and 26 labelled questions for the skill thresholds. The development questions were kept apart from the scored questions, and the scored questions were not read while the engine was tuned.

### 3.2.4 Model Validation and Testing

Six set-ups were tested on the same questions. They were the on-device model alone, the on-device model with plain retrieval, the on-device model with a vector database baseline built on Chroma, the on-device model with the engine, the cloud model alone, and the cloud model with the memory prepared by the engine. The Chroma baseline used the same vault, the same embedding model, and the same limit of 12,000 characters as plain retrieval. Each on-device set-up was run with the main model and with the small model. Every model was run at a temperature of zero.

An answer was scored by its answer key. A knowledge answer was right when it contained every required fact of its key. A reasoning answer was right when its last number equalled the key. Accuracy was the share of right answers in a set-up. The central measure of the study, the fraction of the capability gap closed, was computed for each task type as shown in Equation 3.1, where S is the accuracy of a set-up. The floor is the on-device model alone, the ceiling is the cloud model alone, and the treatment is the on-device model with the engine.

!eq gap | Equation 3.1: Fraction of the capability gap closed.

A value of zero means the engine added nothing. A value of one means the on-device model with the engine matched the cloud model. Where the cloud model was not ahead of the on-device model alone, the measure is not defined and was reported as such.

Cost was measured beside accuracy. Every answer logged the tokens read, the tokens written, the seconds spent before the model was called, and the seconds the model took. Paired differences between set-ups were tested with an exact two-sided sign test, because each answer is simply right or wrong. The engine was frozen as one binary before the first scored run, and the evaluation plan was written down before that run. Faults found after the freeze were reported and were not fixed.

## 3.3 System Development Methodology

The system was developed by incremental prototyping. The work was divided into five increments. Each increment went through analysis, design, build, and evaluation, and each ended with a working version that was measured before the next began. The engine was first prototyped under the working name CAMR in Python and was rebuilt as Burrow in Swift after the Sprint II review of 5 November 2026.

### 3.3.1 Justification

Incremental prototyping suited the study for three reasons. First, the evaluation harness had to exist before the engine, because every part of the engine was judged by what the harness measured. Building it first removed the largest risk of the project, which was reaching the end with no way to produce results. Second, the engine is a chain of separate steps. Adding one step at a time made it possible to measure what each step contributed. Third, the requirements changed during the project. After the review of 5 November, the surfaces through which a person uses the engine were added, and an incremental plan could take them in as one more increment without discarding the measured work.

## 3.4 Methodology Diagram

Figure 3.1 shows the five increments in order. Each box repeats the same four activities, and the label above each box names what that increment delivered.

!fig figures/related/fig3-1-incremental.png | Figure 3.1: Incremental development of the Burrow engine. | 6.0

### 3.4.1 Increment 1: Evaluation Harness

The harness was built first. It loads the questions, runs the on-device and cloud models, scores the answers against their keys, and logs tokens and seconds. It was validated by measuring the gap between the two models with no memory at all.

### 3.4.2 Increment 2: Simplest Treatment

The second increment added the simplest complete memory. Files were indexed with embeddings, pieces were retrieved by search alone, and they were packed into a fixed budget. This version became the control against which the engine was compared.

### 3.4.3 Increment 3: Engine Steps and Skills

The third increment added the parts of the engine one at a time. These were the walk over links between files, the Decide, Fit, Check, and Learn steps, and the skills. Each addition was measured against the control.

### 3.4.4 Increment 4: Device Profiling

The complete engine was profiled on the target laptop. The tokens and the seconds of every answer were measured, with the time spent before the model was called reported separately.

### 3.4.5 Increment 5: Application, Terminal Chat, and MCP Server

The last increment added the surfaces through which the engine is used. These were a native Mac application, a terminal chat, and a Model Context Protocol (MCP) server that opens the same memory to outside models.

## 3.5 System Analysis Diagrams

The analysis followed Object-Oriented Analysis and Design, because the engine was written as a set of types that hold their own data and behaviour. The diagrams were drawn in the Unified Modeling Language (UML). Four analysis diagrams were chosen, and Chapter 4 presents them.

### 3.5.1 Use Case Diagram

The use case diagram shows the boundary of the system, its actors, and what each actor uses the engine for. It was chosen because the engine serves three kinds of actor: a person, a local model, and an outside model or tool. One use case, "Ask a question", is also described in a table.

### 3.5.2 Sequence Diagram

The sequence diagram shows the messages exchanged, in order, when a question is answered. It was chosen because the order of the five steps is the design of the engine. A second sequence diagram shows an outside model using the engine through MCP.

### 3.5.3 Activity Diagram

The activity diagram shows the flow of work from a question to a kept note, with its decision points. Swimlanes separate what the person, the engine, and the local model each do. It was chosen to make clear which party makes each choice.

### 3.5.4 Class Diagram

The class diagram shows the main types of the engine, their operations, and the relationships between them. It was chosen because it maps directly to the Swift code and guided how the library was divided.

## 3.6 System Design Diagrams

Three kinds of design diagram were chosen to show how the system was put together.

### 3.6.1 Database Schema

The database schema shows the tables of the index and how they relate. It was chosen because the index is one SQLite file, and its tables decide what can be searched by words, by meaning, and by links.

### 3.6.2 Wireframes

The wireframes show the layout of the screens before they were built. They cover the main window of the Mac application, the note editor, the step where the person agrees to what is kept, and the terminal chat. They were chosen to plan where the engine's decisions are shown to the person.

### 3.6.3 System Architecture

The system architecture diagram shows the components of the system and their dependencies. It was chosen to show that all memory logic sits in one core library that every surface uses. A diagram of the engine's five steps and a deployment diagram accompany it. The deployment diagram shows which parts run on the laptop and which connections leave it.

## 3.7 Deliverables

The study produced five deliverables.

### 3.7.1 The Burrow Engine Library and Command-Line Tool

A Swift package that implements the vault, the index, and the five steps of the engine, with a command-line tool named `burrow`. Both run entirely on the target laptop.

### 3.7.2 The Mac Application and Terminal Chat

A native Mac application in which a person writes notes, follows their links, and asks questions of the vault. A terminal chat offers the same engine from the command line.

### 3.7.3 The MCP Server

A server that gives outside models and tools the same memory through MCP. Its tool `vault_prepare` and the command `burrow brief` return the engine's decision, a skill, and the excerpts for a task.

### 3.7.4 The Evaluation Harness

A set of Python scripts that run every set-up, score the answers, and write the tables and charts from the logged results. Every experiment in the study can be repeated from the command line.

### 3.7.5 Results and Documentation

The logged results of every run, this report, and the instructions, configuration files, and prompt templates needed to reproduce the results.

## 3.8 Tools and Techniques

### 3.8.1 Swift

The engine, the command-line tool, the terminal chat, the MCP server, and the Mac application were written in Swift. Swift is the native language of the target platform, so the engine runs as one compiled program with no interpreter.

### 3.8.2 SQLite with FTS5

The index is one SQLite database file, which needs no server process. The word index uses the FTS5 full-text extension of SQLite (SQLite, 2026). The embedding vectors are stored in the same file.

### 3.8.3 Ollama and the Local Models

The local models were served by Ollama, which runs quantised open-weight models on consumer hardware (Ollama, 2026). The main model was Gemma 4 12B (Gemma Team, 2026). The small model was Qwen3.5 4B (Qwen Team, 2026).

### 3.8.4 The Hosted API

The cloud reference model, Claude, was reached only through its hosted API. It was pinned to one version for the whole study, so that the ceiling stayed the same across runs.

### 3.8.5 The Embedding Model

Embeddings were produced on the laptop by the qwen3-embedding model at 0.6 billion parameters, served through Ollama (Zhang et al., 2025). The engine and the baseline used the same model.

### 3.8.6 Chroma

Chroma is an open-source vector database (Chroma, 2026). It was run locally to build the vector database baseline of section 3.2.4.

### 3.8.7 LangChain

LangChain is a framework for building applications around language models (LangChain, 2026). An adapter exposes Burrow as a LangChain retriever, so the engine can take the place of a vector database in an existing pipeline.

### 3.8.8 Python

The evaluation harness was written in Python. Python was also used for the scripts that check the answer keys and draw the charts.

### 3.8.9 Git and GitHub

Git was used for version control, and the repository was hosted on GitHub. The state of the code at each evaluation was marked with a tag, so that a result can be traced to the code that produced it.
