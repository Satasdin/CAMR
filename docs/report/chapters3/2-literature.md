# Chapter 2:  Literature Review

## 2.1 Introduction

This chapter reviews the research that the study built on. Section 2.2 describes the current state of on-device language models and external memory: the models themselves, the gap that separates them from cloud models, retrieval and agent memory, and the challenges that remain. Section 2.3 examines eight related systems, five that implement memory for language models and three that Burrow was compared with or built to work beside. Section 2.4 states the gaps those systems leave. Section 2.5 presents the conceptual framework that guided the study.

## 2.2 Current State of On-Device Language Models and External Memory

### 2.2.1 Overview of On-Device Language Models

Kaplan et al. (2020) established that the capability of a language model grows smoothly with its parameter count and its training data, which pushed the field toward large models served from the cloud. A counter-movement followed. Qwen2.5 (Yang et al., 2024), Llama 3.2 (Grattafiori et al., 2024), and Phi-3 (Abdin et al., 2024) were published as open-weight models small enough for an ordinary laptop, and Gunter et al. (2024) described the model that Apple ships on its own devices. J. Xu et al. (2024) reviewed this movement and named lower latency, data that stays local, and personalisation as its reasons.

Each generation moves the same quality into a smaller model. Z. Liu et al. (2024) showed that careful architecture lets models under one billion parameters come close to a seven-billion-parameter model on API-calling tasks. The Gemma 3 report stated that its 4B model was competitive with the previous generation's 27B model (Gemma Team, 2025). The families released in 2026, Gemma 4 (Gemma Team, 2026) and Qwen3.5 (Qwen Team, 2026), include the two models hosted in this study. Lu et al. (2024) measured 70 open small models and reported their ability together with their latency and memory on a device.

### 2.2.2 The Capability Gap and Long-Tail Knowledge

The evidence most important to this study concerns what the gap is made of. Mallen et al. (2023) tested ten models on 14,000 factual questions and found that models struggle with less popular facts and that scaling barely helps in the long tail. Sun et al. (2024) saw the same pattern in 16 public models, which were far from perfect on the rarer entities. Kandpal et al. (2023) traced the cause to training data. Accuracy on a fact depends on how many training documents mention it, and closing the long tail by size alone would need many orders of magnitude more parameters.

Retrieval reduces that dependence. In the study by Mallen et al. (2023), retrieval-augmented models largely outperformed models that were orders of magnitude larger. Soudani et al. (2024) found across twelve models that retrieval beat fine-tuning by a large margin on the least popular facts. Missing knowledge can therefore be supplied from outside a model. This study treated knowledge-bound and reasoning-bound tasks separately for that reason.

### 2.2.3 Retrieval and Agent Memory

Lewis et al. (2020) introduced retrieval-augmented generation, which pairs a generator with an index of retrieved documents, and Fan et al. (2024) surveyed the architectures that followed. Two inexpensive rankings underlie most retrieval. Ranking by word match uses the BM25 function (Robertson & Zaragoza, 2009), and ranking by meaning compares embedding vectors (Karpukhin et al., 2020). Reciprocal rank fusion merges the two lists without training (Cormack et al., 2009). Bruch et al. (2023) showed that a tuned weighted sum of scores can outperform this fusion, but it needs a training set.

Memory extends retrieval from documents to what an agent keeps over time. Sumers et al. (2024) described a language agent as having working, episodic, semantic, and procedural memory. Hu, Liu, et al. (2025) separated agent memory from retrieval-augmented generation and classified it by form, function, and dynamics. Huang et al. (2026) treated portable agent skills as part of memory, and Luo et al. (2026) described three stages of agent memory: storage, reflection, and experience. In these terms Burrow's vault is semantic memory, its decision notes are episodic memory, and its skills are procedural memory.

### 2.2.4 Key Challenges

Four challenges remain. The first is that retrieved text can harm an answer. Yoran et al. (2024) found that retrieval sometimes lowered accuracy across five question-answering benchmarks. Cuconasu et al. (2024) identified the harmful passages as those a retriever scores highly although they do not contain the answer. Reasoning tasks are especially exposed. Shi et al. (2023) saw performance fall dramatically when irrelevant information was added to grade-school mathematics problems, and Mirzadeh et al. (2025) reported drops of up to 65% from a single clause that only seemed relevant.

The second is that more context is not better. Levy et al. (2024) found a notable drop in reasoning at input lengths far shorter than a model's maximum. Hsieh et al. (2024) tested 17 long-context models and found that only half kept satisfactory performance at 32,000 tokens. Jin et al. (2025) showed that output quality first improves and then declines as the number of retrieved passages rises.

The third is trust in what a model does with its context. Joren et al. (2025) found that smaller models often hallucinate or abstain even when the context is sufficient. T. Gao et al. (2023) found that even the best models lacked complete citation support half of the time on one benchmark.

The fourth is that a memory which accepts writes can be attacked. Greshake et al. (2023) showed that instructions hidden in retrieved data can take over an application. Dong et al. (2025) showed that an attacker who can only send queries can plant malicious records in an agent's memory. These findings motivated two design choices in Burrow: every proposed note is backed by the person's own words, and nothing is written to the vault without consent.

## 2.3 Related Works

### 2.3.1 MemGPT

Packer et al. (2023) treated the memory problem as an operating system would. In MemGPT the model's context window is the fast main memory and an external store is the disk, and the system pages information in and out as the conversation demands. This lets a model with a fixed window sustain document analysis and multi-session chat. The design made clear that what a model reads at each step is a policy decision. Later systems took that decision for each question: Adaptive-RAG routes a question to no retrieval, one-step retrieval, or multi-step retrieval (Jeong et al., 2024). MemGPT manages context length, however. It does not measure capability gain for a small model, or token cost and latency on a device. Figure 2.1 shows the two-tier architecture.

!fig figures/related/fig2-1-memgpt.png | Figure 2.1: The MemGPT virtual context architecture. Adapted from Packer et al. (2023). | 6.0

### 2.3.2 Generative Agents

Park et al. (2023) gave simulated agents a memory stream of timestamped observations written in natural language. Each agent retrieved from its stream by combining three scores: relevance to the current situation, recency, and importance. With this memory the agents produced believable long-running behaviour in a simulated town, and the three-part score shaped the retrieval policy first proposed for this study. Zhao et al. (2024) later showed that insights written in natural language and recalled at inference improve an agent without any parameter updates. Generative Agents was designed for simulation and not for question answering, however, and its memory records are verbose. It leaves open how a memory should be read when every token costs time on a device. Figure 2.2 shows the town in which the agents live.

!fig figures/related/fig2-2-generative-agents.png | Figure 2.2: The Smallville environment of Generative Agents. Source: Park et al. (2023). | 5.6

### 2.3.3 MemoryBank

Zhong et al. (2024) added a model of forgetting to long-term memory. MemoryBank strengthens or weakens each stored memory over time in the spirit of the Ebbinghaus forgetting curve. What the system keeps therefore reflects both how often a memory is used and how old it is. The contribution is a principled answer to the question of what should be kept. Hu, Wang, and McAuley (2025) later named selective forgetting as one of four competencies of a memory agent. MemoryBank was evaluated on the quality of long-term companionship behaviour. It does not report capability gain against a larger model, token cost, or latency on a device. Figure 2.3 shows the memory bank, the forgetting curve, and retrieval into the conversation.

!fig figures/related/fig2-3-memorybank.png | Figure 2.3: The MemoryBank framework with updating and forgetting. Source: Zhong et al. (2024). | 6.0

### 2.3.4 HippoRAG

Gutiérrez et al. (2024) built HippoRAG on the hippocampal indexing theory, in which a compact index links the scattered traces of an experience (Teyler & DiScenna, 1986). A language model extracts entities from stored passages into a knowledge graph, and a Personalized PageRank walk spreads relevance from the question to connected passages. HippoRAG improved multi-hop question answering by up to 20% and was 10 to 30 times cheaper than iterative retrieval. A language model must build the graph, however, as in GraphRAG (Edge et al., 2024). Gutiérrez et al. (2025) also noted that graph methods fall considerably below standard retrieval on basic factual memory. Burrow therefore searches the text first and follows links that already exist between files. Figure 2.4 shows the pipeline.

!fig figures/related/fig2-4-hipporag.png | Figure 2.4: HippoRAG offline indexing and online retrieval. Source: HippoRAG project repository (Gutiérrez et al., 2024). | 6.0

### 2.3.5 Mem0

Chhikara et al. (2025) presented Mem0, a memory layer packaged for production use. Mem0 extracts the salient facts from a conversation, consolidates them, and retrieves them at question time. On the LoCoMo benchmark of long conversations (Maharana et al., 2024), the authors reported a 26% relative improvement over OpenAI's memory on a metric judged by a language model. Mem0 is evidence that memory engineering is commercially credible. It writes memories automatically, however, where Burrow proposes a note and waits for consent. It was evaluated on conversational recall, so it does not show how much of the gap between a small and a large model its memory closes for each type of task. Figure 2.5 shows where the memory layer sits in an agent stack.

!fig figures/related/fig2-5-mem0.png | Figure 2.5: The Mem0 memory layer within an agent stack. Source: Mem0 documentation (Chhikara et al., 2025). | 6.0

### 2.3.6 Chroma

Chroma is an open-source vector database (Chroma, 2026). Documents are cut into pieces, and each piece is stored with an identifier, an embedding vector, optional metadata, and its text. At question time the pieces nearest to the question are pasted into the prompt. It runs as an embedded library or as a distributed service. It was the baseline of this study because it is what a developer would build without a memory engine. A vector database is a store and not an engine. It answers every question with its nearest pieces, and Cuconasu et al. (2024) showed that highly ranked pieces without the answer are the ones that hurt. Chroma's own researchers reported that reliability falls as input grows (Hong et al., 2025). Figure 2.6 shows the distributed architecture.

!fig figures/related/fig2-6-chroma.png | Figure 2.6: The architecture of distributed Chroma. Source: Chroma (2026), https://docs.trychroma.com. | 5.8

### 2.3.7 Obsidian

Obsidian is a note-taking application. Its vault is an ordinary folder of plain Markdown files on the person's own disk, and the application adds links between notes without locking them into a database (Obsidian, 2025a). Its graph view draws each note as a circle and each link as a line (Obsidian, 2025b). A-Mem applied the same idea to agents by having a model build a network of linked notes (Xu et al., 2025). Burrow instead starts from the links a person already wrote, in a vault that Obsidian can open. Obsidian is a tool for a person to write and read. It does not select what a language model should read, fit that selection to the model, or measure what the model gains. Figure 2.7 shows the graph view.

!fig figures/related/fig2-7-obsidian.png | Figure 2.7: The graph view of an Obsidian vault. Source: Obsidian (2025b), https://help.obsidian.md/plugins/graph. | 4.8

### 2.3.8 Claude Code and the Model Context Protocol

Claude Code is a coding assistant from Anthropic that reads a codebase, edits files, and runs commands for the developer (Anthropic, 2026a). It keeps a project memory in plain files (Anthropic, 2026b), and it loads written skills in stages so that an unused skill costs little context (Anthropic, n.d.). It reaches outside tools and data through the Model Context Protocol, an open standard between AI applications and data sources (Model Context Protocol, 2026). Hou et al. (2026) catalogued 16 threat scenarios for servers of this protocol. Claude Code is the strongest form of the cloud side of this study. Its model runs in the cloud, so questions and files leave the device. Burrow was built to work beside it through its own protocol server. Figure 2.8 shows the protocol.

!fig figures/related/fig2-8-mcp.png | Figure 2.8: The Model Context Protocol between AI applications and data sources. Source: Model Context Protocol (2026), https://modelcontextprotocol.io. | 6.0

Table 2.1 compares the eight systems by their core idea, their strength, and what each leaves open for the on-device setting.

!tab Table 2.1: Comparison of the related works
!widths 1.3,1.8,1.5,1.7
| System | Core idea | Strength | Limitation for the on-device setting |
| MemGPT (Packer et al., 2023) | Pages context in and out of the window like an operating system | Sustains very long interactions on a fixed window | Manages context length; does not target capability gain or token cost |
| Generative Agents (Park et al., 2023) | Memory stream scored by relevance, recency, and importance | Simple, effective retrieval scoring | Designed for simulation; verbose natural-language records |
| MemoryBank (Zhong et al., 2024) | Memories strengthen and decay over time | Principled forgetting | No accounting of token cost or device latency |
| HippoRAG (Gutiérrez et al., 2024) | Knowledge-graph index walked with Personalized PageRank | Strong multi-hop recall | A language model must build the graph, which is heavy for a device |
| Mem0 (Chhikara et al., 2025) | Salient facts extracted and consolidated into a managed store | Production-ready; gains reported on a long-conversation benchmark | Writes memories without consent; gap closing per task type not measured |
| Chroma (Chroma, 2026) | Vector database queried for the pieces nearest to the question | Simple, runs locally, the standard pipeline | A store, not an engine; same retrieval for every question and every model |
| Obsidian (Obsidian, 2025a) | Vault of plain Markdown notes joined by links | The person owns the files; structure is visible | Made for a person to read; does not supply memory to a model |
| Claude Code (Anthropic, 2026a) | Cloud coding assistant with project memory, extended through the Model Context Protocol | Large model with a memory of the project | Model runs in the cloud; data leaves the device |

## 2.4 Gaps in Related Works

The reviewed work establishes each ingredient separately. Retrieval supplies the long-tail knowledge that small models lack (Kandpal et al., 2023; Mallen et al., 2023). Memory systems store, link, and forget information across long interactions (Chhikara et al., 2025; Packer et al., 2023; Zhong et al., 2024). Methods that decide when to retrieve exist, but Self-RAG needs a specially trained model (Asai et al., 2024) and Adaptive-RAG needs a trained classifier (Jeong et al., 2024). Moskvoretskii et al. (2025) compared 35 such methods and found that simple uncertainty estimates often matched complex pipelines in answer quality.

What is missing is the measurement on a device. Narayan et al. (2025) came nearest. Their on-device model recovered 87% of a cloud model's performance, and 97.9% when the cloud model split the task into small local jobs, but it depended on the cloud throughout. No reviewed work places a memory engine beside a frozen small model on a consumer laptop and reports what fraction of the gap to a cloud model it closes. None reports this separately for knowledge-bound and reasoning-bound tasks, with token and latency accounting, against both a plain vector database and a cloud model. This study addressed that gap.

## 2.5 Conceptual Framework

The framework that structured the study has four parts. The independent variable is the configuration of the memory engine: its Decide, Fit, Check, and Learn steps and the skills it hands to the model with the question. The process is question answering on the device, where the frozen on-device model answers from the question and the memory assembled within the token budget. The dependent variables are the fraction of the capability gap closed, the accuracy gained per token of memory, and the latency on the target device. Task type, knowledge-bound or reasoning-bound, moderates the relationship. The model's weights were held constant, so every measured gain is attributable to the engine. Figure 2.9 presents the framework.

!fig figures/related/fig2-9-framework.png | Figure 2.9: Conceptual framework of the study. | 6.2
