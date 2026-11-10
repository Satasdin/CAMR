# Acknowledgment

I thank God for the strength and good health that carried me through this work. I am grateful to my supervisor, Mr. Tiberius Tabulu, whose patient guidance and honest feedback shaped this project from the proposal to the finished system. I thank the faculty of the School of Computing and Engineering Sciences at Strathmore University for the foundation they gave me, and the Sprint II review panel for asking for something a person can see and use. Finally, I thank my family and friends for their encouragement and support throughout this journey.

# Abstract

Cloud language models are capable, but every question costs money, needs a connection, and sends personal data off the device. Models that run on a consumer laptop are private, offline, and free per question. They are also weaker, most visibly on questions that need facts they have not memorised. Research indicates that this gap is largely missing knowledge, not missing reasoning ability.

This study designed, developed, and evaluated Burrow, a lightweight external memory engine that works beside a frozen on-device model. The memory is a vault of the person's own notes, documents, and code. On every question the engine decides whether the vault is needed, fits the amount of memory to the model within a token budget, and checks the sources an answer cites. Under the Design Science Research paradigm, the engine was built in Swift with an embedded database and delivered with a Mac application, a terminal chat, and a Model Context Protocol server. It was tested on 120 knowledge questions on three curated subjects and 50 reasoning questions from a public benchmark.

On the knowledge questions the on-device model, Gemma 4 12B, answered 9 alone and 102 with Burrow, while the cloud model, Claude, answered 40 alone and 109 with the same memory. On the reasoning questions the on-device model answered 47 alone, 7 with plain retrieval pasted in, and 48 with the engine, which left the memory out of all 50. A memory engine can therefore stand in for model scale on knowledge-bound tasks without harming reasoning.

***Keywords: on-device language models, external memory, retrieval-augmented generation, capability gap, token budget***

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
