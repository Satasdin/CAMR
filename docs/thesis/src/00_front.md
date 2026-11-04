::title::



!A Lightweight External Memory Engine to Bridge the Capability Gap Between On-Device and Cloud Language Models




Ibrahim Sudheysi Ali

166344

ICS 4C




Supervisor Name

Tiberius Tabulu




An Informatics and Computer Science Project Submitted to the School of Computing and Engineering Sciences in Partial Fulfillment of the Requirements for the Award of a Degree in Bachelor of Science in Informatics and Computer Science



School of Computing and Engineering Sciences

Strathmore University

Nairobi, Kenya



November 2026
::title-end::

#! ~Declaration and Approval

I declare that this work has not been previously submitted and approved for the award of a degree by this or any other University. To the best of my knowledge and belief, the project report contains no material previously published or written by another person except where due reference is made in the report itself.

Student Name: Ibrahim Sudheysi Ali

Admission Number: 166344

Student Signature: _________________________   Date: ________________________

The project report of Ibrahim Sudheysi Ali has been reviewed and approved by Tiberius Tabulu, School of Computing and Engineering Sciences, Strathmore University.

Supervisor Signature: _________________________   Date: ________________________

#! ~Abstract

Small language models that run on a laptop keep personal data private, work offline and cost nothing per question, but they know far less than large cloud models and forget everything that falls outside their context window. This study designed, built and evaluated CAMR, a lightweight external memory engine that sits beside a frozen model on an Apple-silicon Mac. CAMR does not store text for the model to read again. It stores the model's own working state: the keys and values that the model writes at every layer while it reads a moment. Related moments are kept together in rooms on the SSD; a question opens the one room it is about, reads it in one burst and lays it in front of the model already read. Three layers share the work: a small core that is always in RAM, the rooms, which move between RAM and the SSD under fixed budgets and go to sleep as words when the disk budget is full, and a vault of plain-text notes that a person can browse. A reach setting decides whether a memory belongs to one session, one project, one agent or everyone.

CAMR was evaluated on the Long Haul, a scripted project history of 2.01 million tokens extended to 4.01 million, with 216 questions graded by rule, against the same models without memory and against Claude Sonnet, Haiku and Opus 5.5 reading as much of the history as fits their one-million-token window. A 4-billion-parameter model with CAMR answered 29 of 73 questions at 2, 3 and 4 million tokens; Claude Sonnet alone answered 32, then 13, then 10. The same model without memory answered 11 to 13 and needed 15.2 GB of RAM; with CAMR the process needed 5.4 to 7.5 GB once the graphics buffer cache was capped. Its first word came in about 0.3 seconds against Claude's 13 to 105 seconds, and the wait did not grow as memory grew from 112 thousand to 2 million tokens. CAMR declined every question about things never told. It did not help with reasoning across two facts or with building a page from a design decided weeks earlier. An earlier text-note version of CAMR, kept as the baseline, showed on public benchmarks that memory closes knowledge gaps but not reasoning gaps.

Keywords: on-device language models; external memory; key–value cache; retrieval; Apple silicon; long context.

#! ~Table of Contents

::toc::

#! ~List of Figures

::lof::

#! ~List of Tables

::lot::

#! ~List of Abbreviations

AI - Artificial Intelligence

API - Application Programming Interface

CAMR - Capability-Adaptive Memory Retrieval, the memory engine of this study

CPU - Central Processing Unit

DSR - Design Science Research

GB - Gigabyte (10^9 bytes); GiB - Gibibyte (2^30 bytes)

GPU - Graphics Processing Unit

HTTP - Hypertext Transfer Protocol

JSON - JavaScript Object Notation

KV - Key–Value (the keys and values a transformer layer keeps for each token it has read)

LLM - Large Language Model

LRU - Least Recently Used

MCP - Model Context Protocol

MLX - Apple's array framework for machine learning on Apple silicon

QA - Question Answering

RAG - Retrieval-Augmented Generation

RAM - Random Access Memory

RoPE - Rotary Position Embedding

SLM - Small Language Model

SSD - Solid-State Drive

TTFT - Time to First Token (the wait for the first word)

UML - Unified Modeling Language

::frontmatter-end::
