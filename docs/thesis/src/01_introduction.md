# Introduction {#intro}

## Background Information {#background}

Language models have become the foundation of modern conversational software, powering assistants that answer questions, summarise documents and help with everyday tasks. The most capable of these models contain tens or hundreds of billions of parameters and run as cloud services on specialised hardware. Their capability comes at a cost: every query travels over a network, personal data leaves the user's device, the service fails without connectivity, and each request carries a price. Empirical work on scaling has shown that capability grows predictably with model size and training data (Kaplan et al., 2020), which is precisely why the strongest models are also the largest and the least practical to run locally.

A parallel movement has formed around small language models, typically between one and eight billion parameters, that run directly on consumer hardware such as laptops and phones. Recent small models such as Qwen2.5 (A. Yang et al., 2024), Qwen3 (A. Yang et al., 2025), Llama 3.2 (Grattafiori et al., 2024), Phi-3 (Abdin et al., 2024), and the on-device foundation models that Apple ships on its consumer chips (Gunter et al., 2024) show that useful language ability fits in the memory of an ordinary computer. On-device deployment offers real advantages: answers are generated locally with low latency, private data never leaves the machine, the assistant keeps working offline, and the marginal cost of a query is zero. A recent survey confirms both the rapid progress of small models and their persistent weaknesses relative to their larger counterparts (Lu et al., 2024).

The most consistent of those weaknesses is knowledge. A small model has not memorised as many facts as a large one. Mallen et al. (2023) showed this directly: language models struggle with less popular, long-tail facts, retrieval of external text helps significantly in exactly those cases, and making models bigger mainly improves recall of popular facts while barely improving the long tail. If much of the gap between small and large models is missing knowledge rather than missing reasoning, then supplying the right knowledge at the right time, from outside the model, can recover a meaningful share of the gap without touching the model at all.

A second weakness matters as soon as an assistant is used for long work. A model only sees what is in its context window, and on a laptop the window is limited by memory: the keys and values a transformer keeps for every token it has read grow with the history. Cloud models now read up to a million tokens at once, while a small local model with a 64,000-token window already needed 15.2 GB of RAM in this study (Section {sec:haul-results}). A project that runs for months produces far more than either window holds, so both kinds of model forget its beginning.

This study designed, built and evaluated CAMR (Capability-Adaptive Memory Retrieval), a lightweight external memory engine that sits beside a frozen language model on a consumer laptop. CAMR was built in two versions. The first, kept in this report as the baseline (CAMR v1), stored short text notes in an embedded database and gave the model the few that matched each question; it was evaluated on public question-answering benchmarks. The engine reported here keeps the model's own working state instead: while the model reads a moment, it writes its keys and values at every layer, and CAMR saves them to the SSD in rooms of related moments. A question opens one room, reads it in one burst and lays it in front of the model already read, so the model continues as if it had just read those moments. The model's weights are never changed. The study then measured, separately for different kinds of question, how much of the gap between a small on-device model and a large cloud model this memory closes, and at what cost in time, RAM and disk.

## Problem Statement {#problem}

Users who want a private, offline, low-cost assistant must accept a small on-device model, and with it a marked drop in capability, most visibly on questions that require knowledge the small model has not memorised and on long work whose history no longer fits in its context window. The two standard remedies do not fit the on-device setting. Replacing the small model with a larger one defeats the purpose, because the larger model no longer fits on the device. Fine-tuning the small model on new knowledge requires compute that ordinary users do not have, must be repeated whenever knowledge changes, and risks degrading the model's existing abilities.

Retrieval-augmented approaches offer a third path: leave the model frozen and supply relevant text at question time. The research literature has established the ingredients separately. Retrieval can substitute for model scale on knowledge-heavy tasks (Lewis et al., 2020; Borgeaud et al., 2022; Izacard et al., 2023). Memory systems can accumulate and organise information across long interactions (Packer et al., 2023; Zhong et al., 2024; Gutierrez et al., 2024). Prompts can be compressed so that less text carries the same meaning (Jiang et al., 2023), and a model's keys and values can be reused instead of recomputed (Gim et al., 2024). What no existing work provides is a measured answer to the question that matters for on-device deployment: when these ingredients are combined into a memory engine beside a frozen small model on a real consumer device, what fraction of the small-versus-large capability gap is actually recovered, on which kinds of tasks, and at what cost in time, RAM and storage as the memory grows? Without that answer, designers of on-device assistants cannot know whether memory engineering is a worthwhile substitute for model scale, or where its limits lie.

## Objectives {#objectives}

This section states the general objective of the study and breaks it down into the specific objectives that guided the work.

### General Objective

The general objective of this study was to design, implement and experimentally evaluate a lightweight external memory engine for a frozen small language model on a consumer laptop, in order to measure how much of the capability gap between on-device and cloud language models such an engine bridges, by task type, with the time and memory cost of every answer.

### Specific Objectives {#specific-objectives}

1. To investigate existing memory, retrieval and compression techniques for language models and establish their applicability and limitations in the on-device setting.
2. To design a lightweight memory engine for a frozen small language model, comprising a write path that turns what the user tells it into stored memory, a read path that finds the memory a question needs, and a budget that controls how much memory the model reads.
3. To implement the designed engine on a consumer laptop with no dedicated graphics card, so that the model and its memory run entirely on the device and the memory can grow on local storage.
4. To evaluate the implemented engine experimentally against the same model without memory and against a large cloud model, separately for knowledge-bound and reasoning-bound tasks, together with the time to the first word, the RAM and the storage of every answer.
5. To determine how much memory the model should read, and what each component of the engine contributes, through controlled comparisons in which one choice is varied at a time.

## Research Questions {#rqs}

The study sought to answer the following research questions, one for each specific objective:

1. What memory, retrieval and compression techniques exist for language models, and what are their limitations in the on-device setting?
2. How should a lightweight engine keep and find memory for a frozen small model so that the model can use it?
3. Can such an engine run on a consumer laptop with a memory that grows without making the model slower or heavier?
4. How much of the capability gap between a small on-device model and a large cloud model does the engine bridge, does it help more on knowledge-bound than on reasoning-bound tasks, and at what cost?
5. How much memory should the model read, and what does each component of the engine contribute?

## Justification {#justification}

The study matters for three audiences. For users, especially in settings where connectivity is unreliable or data privacy is a serious concern, a more capable on-device assistant means useful AI that works offline, keeps personal data local and costs nothing per query. For developers of on-device assistants, the study provides what the literature lacked: a measured, component-by-component account of how far memory engineering can substitute for model scale and for a long context window, allowing informed decisions about where to invest effort. For the research community, the study contributes an evaluation method, a scripted long project graded by rule in which every answer records what it cost, against which future memory systems can be compared.

The study was also deliberately scoped to be feasible as a final-year undergraduate project. The language models themselves were reused, not trained, so the original work lies in the design of the engine and the design of the measurement, both of which were achievable on a single consumer laptop with modest API credits for the large reference models.

## Scope {#scope}

The deployment target was a consumer laptop with no dedicated graphics card. Development began on a MacBook Air M4 with 16 GB of unified memory, and every reported measurement of the engine was made on a MacBook Pro M5 Pro with 24 GB. Both use Apple silicon, whose integrated graphics processor runs the models through Apple's MLX framework (Hannun et al., 2023); the baseline ran on CPU-only machines with 16 GB. The small models studied were open-weight Qwen3 models of 1.7, 4 and 8 billion parameters, run locally and frozen; a 27-billion-parameter model was run on the same Mac as a larger local comparison, and the Ollama runtime was paired with the engine to test memory supplied as words. The large reference models were Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5, reached through a cloud API and never run locally; they answered the same questions alone and served only as the yardstick. The baseline's reference was Kimi K3.

Evaluation used English material of three kinds: a scripted project history of 2 to 4 million tokens with questions graded by rule (the Long Haul), public benchmarks from the Hugging Face Hub (MATH-500, AIME, HARP and BABILong), and, for the baseline, the public question-answering benchmarks PopQA, HotpotQA, 2WikiMultiHopQA and GSM8K. Together they separate knowledge-bound from reasoning-bound performance. The system delivered is the memory engine, its benchmarks and their records, and a native Mac application with two parts, Chat and Code, that shows the engine at work. It is a research prototype, not a commercial product.

## Limitations and Delimitations {#limits}

The limitations of the study are the constraints it operated under. Timings and memory figures were measured on one Mac and may differ on other hardware, so device results are indicative rather than universal. The cloud reference models are commercial services whose behaviour can change between versions; the study pinned the model identifiers, recorded them in every record and logged every call. The main test is a scripted project, built to be hard in known ways; it is an approximation of real work, and its findings generalise to live use only to the degree that the script represents it.

The delimitations are boundaries the study deliberately drew. No language model was trained or fine-tuned in the engine; all weights remained frozen, since the research question is precisely what memory achieves without touching the model (the baseline trained two adapters only as a comparison). The engine was not ported to mobile phones or to computers other than Apple-silicon Macs; the laptop target preserves the on-device claim while avoiding toolchain work that adds engineering effort without research value. A graph-based associative layer in the style of Gutierrez et al. (2024) was treated as optional; the baseline implemented a light form of it as entity bridging. No study with real users was carried out. Finally, the study is limited to English text; a first test of memory for documents, images and video is reported, but multilingual memory is left to future work.
