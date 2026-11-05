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

Small language models on a laptop keep data private, but they know far less than cloud models and forget whatever falls outside their context window. Retrieval-augmented generation (RAG) narrows this gap by pasting retrieved text into the prompt, which the model must re-read at every question.

This study designed, implemented and evaluated CAMR, a lightweight external memory engine for a frozen small model on a Mac. CAMR keeps the model's own keys and values for what it is told in rooms on the SSD and lays the one room a question needs in front of the model already read. It was delivered as a native Mac chat application and evaluated experimentally on the Long Haul, a scripted 2-to-4-million-token project history, against the same models without memory, RAG over the same memory, and Claude models reading their full window.

A 4-billion-parameter model with CAMR answered 29 of 73 questions at 2, 3 and 4 million tokens, against 32, 13 and 10 for Claude Sonnet alone and 11 for the model alone. Its first word came in 0.2 to 0.3 seconds, against 13 to 105 seconds for Sonnet and Opus, in 5 to 8 GB of RAM, and did not slow as memory grew. Against RAG, CAMR was as accurate, answered sooner and completed three times as many tool errands. Memory closed knowledge gaps, not reasoning gaps. A laptop model with a memory of its own notes can therefore rival cloud models on long personal histories.

***Keywords:*** ***on-device language models; external memory; key–value cache; retrieval-augmented generation; Apple silicon; long context***

#! ~Table of Contents

::toc::

#! ~List of Figures

::lof::

#! ~List of Tables

::lot::

#! ~List of Equations

::loe::

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
