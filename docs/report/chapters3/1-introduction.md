# Chapter 1:  Introduction

## 1.1 Background Information

Language models now sit behind most conversational software. Kaplan et al. (2020) showed that the capability of a language model grows predictably with its size and its training data. The strongest models are therefore the largest, and they run as cloud services. Every question sent to them travels over a network and leaves the person's device. Z. Zhang et al. (2024) studied real conversations with a cloud assistant and interviewed 19 of its users. They found that people constantly trade privacy against usefulness, and that wrong mental models limit their grasp of the risk.

A second family of models runs directly on consumer hardware. J. Xu et al. (2024) reviewed these on-device models and gave three reasons for running a model locally: lower latency, data that stays on the device, and personalisation. Lu et al. (2024) measured 70 open models of up to five billion parameters and reported both what they can do and what they cost to run on a device. The open-weight families released in 2026, Gemma 4 (Gemma Team, 2026) and Qwen3.5 (Qwen Team, 2026), include models sized for a laptop.

The weakness of a small model is concentrated in what it knows. Mallen et al. (2023) showed that language models struggle with less popular facts and that scaling a model up barely helps on this long tail. Kandpal et al. (2023) explained why. A model's accuracy on a factual question depends on how many training documents mention the fact, and a model would need to grow by many orders of magnitude to answer rarely supported questions well. A person's own notes, documents, and code are the extreme case, because no model saw them in training.

Knowledge of this kind can be supplied from outside the model. Lewis et al. (2020) introduced retrieval-augmented generation, which pairs a model with an index of documents that it reads at answer time. Soudani et al. (2024) compared this approach with fine-tuning across twelve language models and found that retrieval won by a large margin on the least popular facts. If much of the gap between small and large models is missing knowledge, an external memory might recover a meaningful share of it without changing the model.

## 1.2 Problem Statement

A person who wants a private, offline, low-cost assistant must accept a small on-device model. With it comes a marked drop in capability, most visibly on questions that need facts the model has not memorised. The two standard remedies do not fit the device. A larger model no longer fits in the machine's memory. Fine-tuning the small model needs extensive resources (Soudani et al., 2024) and must be repeated whenever the knowledge changes.

Retrieval is the third path, but pasting retrieved text into every prompt is not safe. Yoran et al. (2024) found across five question-answering benchmarks that retrieval sometimes lowered accuracy when the retrieved text was irrelevant. Shi et al. (2023) added irrelevant information to grade-school mathematics problems and saw model performance fall dramatically. Levy et al. (2024) showed that reasoning drops at input lengths far shorter than a model's technical maximum. A memory beside a small model must therefore decide when to supply text and how much. Published remedies fine-tune the model or train a classifier (Jeong et al., 2024; Yoran et al., 2024).

It is also not known how much of the gap such a memory closes. Narayan et al. (2025) came nearest: a small on-device model that read local documents recovered 87% of a cloud model's performance, but only by working with the cloud model. No study found in the literature measures what memory alone achieves on a consumer device, by task type, and at what cost. This study therefore developed Burrow, a lightweight external memory engine that sits beside a frozen on-device model and gives it a vault of the person's own notes, documents, and code. The study then measured how much of the capability gap this memory closed, separately for knowledge-bound and reasoning-bound tasks, and at what cost in tokens and latency.

## 1.3 Research Objectives

### 1.3.1 General Objective

The general objective of this study was to design, develop, and validate a lightweight memory engine for a frozen small language model on a consumer laptop, in order to quantify how much of the capability gap between small on-device and large cloud language models such a memory engine can close, by task type, under explicit token and latency accounting.

### 1.3.2 Specific Objectives

i) To investigate the capability gaps between large, small, and on-device language models, together with existing memory, retrieval, and compression techniques and the interaction between a model's internal (parametric) and external (retrieved) knowledge, so as to establish their applicability and limitations in the on-device setting.
ii) To design a lightweight memory engine for a frozen small language model, comprising a write policy that distils interactions into compact stored notes, a retrieval policy that ranks stored passages by word match and by meaning and follows the links between files, and a token budgeting mechanism that controls how much memory the model reads.
iii) To develop the designed memory engine in Swift on an Apple-silicon consumer laptop with no dedicated graphics card, using an embedded database as the index of the memory store.
iv) To evaluate the implemented engine experimentally by measuring the fraction of the capability gap between a small local model and a large cloud model that the engine closes, separately for knowledge-bound and reasoning-bound tasks, together with the token cost and latency of every answer.
v) To determine the token budget that maximises the fraction of the capability gap closed per token, so that the engine can be configured for the best accuracy-to-cost trade-off on a resource-constrained device.

## 1.4 Research Questions

i) What memory, retrieval, and compression techniques exist for language models, and what are their limitations in the on-device setting?
ii) How much of the capability gap between a small on-device language model and a large cloud language model can a frozen-weights memory engine close?
iii) Does the memory engine help more on knowledge-bound questions than on reasoning-bound questions?
iv) What context token budget maximises the fraction of the capability gap closed per token, and how does gap closure scale as the budget increases?
v) What is the cost of the memory engine in tokens and latency when measured on a consumer laptop?

## 1.5 Justification

The study serves three groups. People who handle private material gain an assistant that keeps it on their own machine. Mireshghallah et al. (2024) found personal information in 16% of code-editing conversations with commercial chat models, which is the kind of material a vault of notes and code holds. In Kenya, personal data falls under the Data Protection Act (2019), and Ogonjo (2025) noted that data and AI sovereignty are reflected in the national AI strategy. Developers of on-device assistants gain a measured account of how far memory engineering can stand in for model scale. Researchers gain an evaluation method, the gap-closed measure reported per task type with token and latency accounting on consumer hardware, against which later memory systems can be compared.

## 1.6 Scope

The study targeted one consumer laptop, an Apple MacBook Pro with an M5 Pro chip, 24 gigabytes of shared memory, and no dedicated graphics card. The on-device models were open-weight models run locally through Ollama: Gemma 4 12B as the main model and Qwen3.5 4B as the small model. The cloud model, Claude, served only as the upper reference. The evaluation used English questions of two kinds: knowledge questions on three curated subjects that the on-device model cannot know well, and mathematical reasoning questions from a public benchmark. The system delivered was the memory engine, its evaluation harness, and four ways to use it: a command-line tool, a native Mac application, a terminal chat, and a Model Context Protocol server.

## 1.7 Limitations and Delimitations

### 1.7.1 Limitations

Four constraints outside the study's control shape how the findings should be read.

i) Latency was measured on one consumer laptop and may differ on other machines.
ii) The cloud reference model is a hosted service whose behaviour may change over time, which can move the ceiling used to calculate the capability gap.
iii) The questions on the curated subjects were written by a language model from the source documents and not by people, so the results may not transfer equally to every live use.
iv) The cost and time available to one undergraduate project limited how many models, devices, languages, and modalities could be tested.

### 1.7.2 Delimitations

The study narrowed its focus on purpose. It fixed one laptop as the target device and reported the full hardware specification and the seconds taken by every answer. It pinned and logged one version of the cloud model for the whole experiment. It used three unrelated subjects and one public benchmark, and it reported single-fact, multi-fact, and mathematical reasoning results separately. It did not train or fine-tune any language model, did not port the engine to mobile phones, and did not evaluate multilingual or multimodal memory. The graph-based retrieval layer that the proposal held back as optional was built in a light form, as a walk over the links that already exist between files.
