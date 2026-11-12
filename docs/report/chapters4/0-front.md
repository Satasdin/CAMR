# Acknowledgment

I thank God for the strength and good health that carried me through this work. I am grateful to my supervisor, Mr. Tiberius Tabulu, whose patient guidance and honest feedback shaped this project from its first idea to the finished system. I thank the faculty of the School of Computing and Engineering Sciences at Strathmore University for the foundation they gave me, and the Sprint II review panel for asking for something a person can see and use. Finally, I thank my family and friends for their encouragement and support throughout this journey.

# Abstract

Cloud language models are capable, but each question costs money and sends personal data off the device. Models on a consumer laptop are private and free per question, but weaker on facts they have not memorised: a gap of knowledge more than of reasoning.

This study designed, developed, and evaluated Burrow, an external memory engine that gives a frozen on-device model a vault of the person's own notes, documents, and code. For each question the engine decides whether the vault is needed, fits what it shows to the model's token budget, and checks an answer's citations. Following Design Science Research, it was built in Swift with an embedded database, reached through a desktop application and a Model Context Protocol server, and tested on 120 knowledge and 50 reasoning questions.

On knowledge questions the on-device model, Gemma 4 12B, answered 9 alone and 102 with Burrow, against 109 for the cloud model, Claude, given the same vault. On reasoning questions plain retrieval cut it from 47 to 7 correct; the engine left the memory out, and it answered 48. A local model with a well-prepared memory can therefore approach a cloud model on private knowledge, if memory is withheld from reasoning.

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
