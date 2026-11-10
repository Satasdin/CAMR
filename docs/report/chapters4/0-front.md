# Acknowledgment

I thank God for the strength and good health that carried me through this work. I am grateful to my supervisor, Mr. Tiberius Tabulu, whose patient guidance and honest feedback shaped this project from the proposal to the finished system. I thank the faculty of the School of Computing and Engineering Sciences at Strathmore University for the foundation they gave me, and the Sprint II review panel for asking for something a person can see and use. Finally, I thank my family and friends for their encouragement and support throughout this journey.

# Abstract

Cloud language models are capable, but every question costs money, needs a connection, and sends personal data off the device. Models on a consumer laptop are private, offline, and free per question, but weaker on facts they have not memorised. Research indicates that this gap is largely missing knowledge, not missing reasoning ability.

This study designed, developed, and evaluated Burrow, a lightweight external memory engine that works beside a frozen on-device model. The memory is a vault of the person's own notes, documents, and code. On every question the engine decides whether the vault is needed, fits the amount of memory to the model within a token budget, and, on the command line, checks the sources an answer cites. Under the Design Science Research paradigm, the engine was built in Swift with an embedded database, a desktop application, a terminal chat, and a Model Context Protocol server. It was tested on 120 knowledge questions on three curated subjects and 50 reasoning questions from a public benchmark.

On the knowledge questions the on-device model, Gemma 4 12B, answered 9 alone and 102 with Burrow, while the cloud model, Claude, answered 40 alone and 109 with the same vault. On the reasoning questions it answered 47 alone, 7 with plain retrieval pasted in, and 48 with the engine, which left the memory out of all 50. Given the same vault, an on-device model can therefore approach a large cloud model on knowledge-bound tasks, provided the memory is withheld from reasoning questions.

***Keywords: on-device language models, external memory, retrieval-augmented generation, capability gap, token budget***

# Table of Contents

!toc TOC \o "1-3" \h \z \u

# List of Figures

!toc TOC \h \z \c "Figure"

# List of Tables

!toc TOC \h \z \c "Table"

# List of Equations

!toc TOC \h \z \c "Equation"

# List of Abbreviations

AI - Artificial Intelligence
API - Application Programming Interface
BM25 - Best Matching 25
DSR - Design Science Research
FTS5 - Full-Text Search version 5 (SQLite)
GSM8K - Grade School Math 8K
JSON - JavaScript Object Notation
JSON-RPC - JSON Remote Procedure Call
LLM - Large Language Model
MCP - Model Context Protocol
OOAD - Object-Oriented Analysis and Design
RAG - Retrieval-Augmented Generation
RRF - Reciprocal Rank Fusion
SLM - Small Language Model
SQL - Structured Query Language
SSD - Solid-State Drive
UML - Unified Modeling Language
