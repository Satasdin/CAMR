# Acknowledgment

First and foremost, I thank God for the guidance, strength, and good health that carried me through this work. I am sincerely grateful to my supervisor, Mr. Tiberius Tabulu, for his steady guidance, patience, and constructive feedback, which shaped the direction of this project from the proposal to the finished system. I also thank the faculty of the School of Computing and Engineering Sciences at Strathmore University for the foundation they have given me, and the panel of the Sprint II review for the feedback that turned the engine into something a person can see and use. Finally, I am deeply thankful to my family and friends for their encouragement and unwavering support throughout this journey.

# Abstract

In recent years, large language models (LLMs) served from the cloud have demonstrated remarkable capabilities in conversational software, but their deployment incurs significant financial cost, latency, and data privacy concerns. Language models that run directly on consumer devices offer an offline, low-cost, and private alternative, yet they suffer from a marked drop in capability, most visibly on tasks requiring factual knowledge that they have not memorized. Research indicates that this gap is largely due to a lack of factual knowledge rather than reasoning capacity.

To address this challenge, this study designed, developed, and evaluated Burrow, a lightweight external memory engine that operates beside a frozen on-device model on a consumer laptop. The memory is a vault of the person's own notes, documents, and code. On every question the engine decides whether the vault is needed, fits the amount of memory to the hosted model within a token budget, lets the model answer, checks every source the answer cites, and proposes notes of what was decided. Operating under the Design Science Research (DSR) paradigm, the engine was implemented in Swift with an embedded database and delivered with a Mac application, a terminal chat, and a Model Context Protocol server. The same tasks were given to an on-device model alone, to the on-device model with Burrow, to a cloud model, and to a standard vector database pipeline, separately for knowledge-bound and reasoning-bound tasks. [PENDING: results sentence]

***Keywords: on-device language models, small language models, external memory, retrieval-augmented generation, capability gap, token budget, design science research***

# Table of Contents

!toc TOC \o "1-3" \h \z \u

# List of Figures

!toc TOC \h \z \t "FigCaption,1"

# List of Tables

!toc TOC \h \z \t "TabCaption,1"

# List of Equations

!toc TOC \h \z \t "EqCaption,1"

# List of Abbreviations

AI - Artificial Intelligence
API - Application Programming Interface
BGE - BAAI General Embedding
BM25 - Best Matching 25
CPU - Central Processing Unit
DSR - Design Science Research
EM - Exact Match
F1 - F-Score (Harmonic Mean of Precision and Recall)
FTS5 - Full-Text Search version 5 (SQLite)
GPU - Graphics Processing Unit
GSM8K - Grade School Math 8K
JSON - JavaScript Object Notation
KG - Knowledge Graph
LLM - Large Language Model
MCP - Model Context Protocol
OD - On-Device
PPR - Personalized PageRank
QA - Question Answering
RAG - Retrieval-Augmented Generation
RAM - Random Access Memory
RRF - Reciprocal Rank Fusion
SLM - Small Language Model
SQL - Structured Query Language
SWE-bench - Software Engineering Benchmark
