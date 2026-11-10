# Chapter 2:  Literature Review

## 2.1 Introduction

This study addresses a specific problem. A developer who cannot send private code to a cloud assistant can run a language model on their own computer, but that model begins every session knowing nothing of the project, and much of what the developer needs to know, in particular why the code was built as it was, was never written into the code. Burrow, the system developed in this study, is a private macOS application in which a folder of Markdown notes forms a vault, code folders are linked in read-only unless a person accepts a proposed change, and a local model receives only the excerpts a question needs.

This chapter grounds that work in existing scholarship. It establishes what is known about using local models on private projects, how other systems have supplied project knowledge to language models, how strong the evidence for those systems is, and what remains unaddressed. The chapter also prevents duplication by identifying the systems closest to Burrow and justifies the need for the study.

The review is organised thematically and follows the first three objectives of the study. The themes are the state of local models and their challenges, the existing memory and code retrieval systems, and the gaps between them. Objectives iv and v, which concern the design, development and testing of Burrow, are combined in the conceptual framework, since both depend on the same variables.

The works reviewed comprise peer-reviewed journal articles and conference papers, surveys, benchmark studies, international standards and specifications, and, because the field moves faster than its publication cycle, preprints and the release documentation of open-source tools. Sources were selected by three criteria: relevance to private, project-level memory for language models; publication date; and methodological rigour, judged by the clarity of the evaluation, who carried it out and whether a baseline was used. Preprints and self-reported results are named as such wherever they are used.

The review focuses on works from the last three years in the best case and the last five years in the worst case, meaning 2023 onward by preference and 2021 onward at the earliest. Older works appear only where they are the origin of a method or concept that the study actually uses. These are the BM25 ranking function (Robertson & Zaragoza, 2009), reciprocal rank fusion (Cormack et al., 2009), the concept of knowledge vaporisation (Jansen & Bosch, 2005), the ideals of local-first software (Kleppmann et al., 2019), and information foraging theory and its application to programmers (Pirolli & Card, 1999; Lawrance et al., 2013).

Section 2.2 examines the current state of local language model use on private software projects and addresses objective i. Section 2.3 studies how existing memory and code retrieval systems have given language models knowledge of a project and addresses objective ii. Section 2.4 draws out the challenges and gaps that remain in those systems and addresses objective iii. Section 2.5 presents the conceptual framework that links the review to objectives iv and v.

## 2.2 Current State of Local Language Models on Private Software Projects

**Alignment with Objective i:** To analyse the current state of local language model use on private software projects, and the challenges involved.

### 2.2.1 Overview of Local Language Model Use

**Definition.** Local language model use on a private software project means running a language model on hardware the developer controls, so that source code, notes and prompts are processed on that hardware and are not sent to a third party. The vendor of one widely used runtime states that it does not see prompts or data when a model runs locally, while prompts sent to its optional cloud models are processed by the company in order to provide the service (Ollama, 2026b). Privacy is therefore a property of a particular configuration and not of a product, and that statement is the vendor's own and has not been independently audited.

**Current approaches.** Four approaches can be distinguished, and they are often combined. The first is the cloud coding assistant, which is the point of comparison for everything else. In the 2025 Stack Overflow Developer Survey, 47.1% of the 33,662 people answering reported using AI tools daily (Stack Overflow, 2025). The second is the local runtime and open-weight model. Qwen3 is a family of models from 0.6 to 235 billion parameters, released under an open licence, with a thinking mode that lets latency be traded against performance (Yang et al., 2025). Quantisation, which stores a model's weights at lower precision, is what makes such models practical on modest hardware (Giagnorio et al., 2025).

The third approach is retrieval-augmented generation, in which a model is given text drawn from an external store at the moment of asking, so that its knowledge can be extended and updated without retraining (Gao et al., 2023). At repository scale this has become its own field. A recent survey treats retrieval-augmented code generation as an evolving process of context construction, retrieval, generation and interaction with the environment, rather than as a fixed pipeline, and organises the work by what is searched, by what controls the search, and by how it is evaluated (Tao et al., 2025). The fourth approach is persistent memory for agents, in which what an agent has seen or done is stored and brought back in later sessions. A survey of this area argues that memory is the component that makes long-term interaction between agents and their environment possible, and it notes that earlier work lacked a holistic comparison (Z. Zhang et al., 2024).

**Efficacy: successes.** The evidence shows that models small enough for local use can be serviceable. In a study of code models, quantisation to 4-bit precision reduced the memory footprint by 70% on average with no significant fall in performance (Giagnorio et al., 2025). A fine-tuned open-weight model, Qwen-2.5-Coder-Instruct-32B, performed comparably to leading proprietary models at finding the code relevant to an issue, at about 86% lower cost (Chen et al., 2025). Retrieval also delivers measurable gains on code: splitting code along its syntax structure instead of by line improved Recall@5 by 4.3 points on RepoEval and Pass@1 by 2.67 points on SWE-bench (Y. Zhang et al., 2025).

**Efficacy: limitations.** These successes are narrower than they appear. Giagnorio et al. (2025) compare a quantised model with its own full-precision version on code generation benchmarks, which shows that quantisation costs little and says nothing about how a small model compares with a large one. Chen et al. (2025) measure a single task, localisation, after fine-tuning a model for that task. On real development work the picture is less favourable. In a case study of one developer on one production codebase over two consecutive 28-day periods, 74.9% of commits made with a quantised on-premise model were repairs, against 45.9% with a cloud model, at similar code churn (Peng et al., 2026). That study is a non-randomised preprint and cannot be generalised, yet it is one of very few comparisons made on real work and not on benchmarks, and it points in the opposite direction from the benchmark results. Whole-repository tasks are also harder than functions: when SWE-bench introduced 2,294 problems drawn from real GitHub issues, the best model of that time solved 1.96% of them (Jimenez et al., 2024). The current state is therefore that local models are capable of useful work on bounded tasks, but that their capacity on sustained project work is unproven and probably lower than that of cloud models.

### 2.2.2 Key Challenges

**Privacy concerns about cloud assistants.** Adoption is high and so is unease. Of 31,877 respondents answering on AI agents in the 2025 Stack Overflow survey, 56.1% strongly and 25.3% somewhat agreed that they worry about data security and privacy (Stack Overflow, 2025). The survey is not peer-reviewed, relies on a self-selected sample and asks about agents in general and not about cloud against local deployment, so it establishes concern and not avoidance of the cloud. Klemmer et al. (2024) provide more direct evidence. In 27 interviews with software engineers, team leads and security testers, and in an analysis of 190 Reddit posts and comments, most participants named leaking sensitive data to third-party assistants as their main concern. A few reported company bans made mainly for privacy reasons, about half said that their company had no policy on AI at all, and a few used a local model for sensitive or proprietary code. A survey of 481 programmers found that the reasons for not using assistants include trust, company policies and the assistant's lack of project-size context (Sergeyuk et al., 2025).

Taken together, these sources reveal a tension. Daily use and widespread worry coexist, so concern alone does not stop adoption, and the developers most directly affected may be those whose employers restrict use, who are invisible in a survey about tool use. The risk is also more than a perception. Huang et al. (2024) showed that commercial code completion tools can reproduce exact training data and leak secret strings, and they identified two valid credentials in their experiments, although that study concerns what was already memorised in training and not what a developer submits while working.

**Capability limits of local models.** As Section 2.2.1 showed, the evidence on capability conflicts because the studies measure different things. Technical reports on model families such as Qwen3 report strong results on code benchmarks, but these are the developers' own results (Yang et al., 2025). The practical consequence for this study is that a small local model may fail a task even when it is given the correct context. Any memory system tested on such a model is therefore limited by the model, and a null result cannot distinguish a poor memory from a model that could not use a good one.

**Context limits.** A language model can only attend to the text placed in its context window, and on local hardware that window is small by default. Ollama's default depends on available graphics memory: 4,096 tokens below 24 GiB, 32,768 tokens up to 48 GiB and 262,144 tokens above that (Ollama, 2026a). Long windows, even where available, are not a complete remedy. Liu et al. (2024) found that models perform best when relevant information sits at the start or end of an input and that performance falls when it sits in the middle, even for models designed for long contexts. LongMemEval, a peer-reviewed benchmark of 500 questions on memory across sessions, reported a 30% fall in accuracy for commercial assistants and long-context models when recalling information across sustained interactions, and it includes abstention, meaning declining a question whose answer is not known (Wu et al., 2025). LoCoMo, with conversations of up to 32 sessions, found that long-context models and retrieval both help and both still fall well short of human performance (Maharana et al., 2024). Whether retrieval or a long context is preferable for repository work remains an open question (Tao et al., 2025).

**Retrieval limits.** Retrieval can only return what the index can find, and each approach has known weaknesses. Word search through the BM25 ranking function remains a strong baseline (Robertson & Zaragoza, 2009), and it is built into SQLite's FTS5 extension (SQLite, 2026). Reciprocal rank fusion merges several rankings using only the ranks (Cormack et al., 2009), which is the method that Burrow uses to merge word search with embedding search. The method is contested: Bruch et al. (2023) found that a convex combination of scores outperformed reciprocal rank fusion and that the latter is sensitive to its parameters. Convex combination, however, needs a set of labelled examples to tune its weight, and a person's own vault offers no such set, so the finding identifies a cost of the method without removing the reason for using it. A further limit is that similarity to a question is not the same as relevance to it: a file may be essential because another file imports it, and share no words with the question. Moreover, retrieved material that is not relevant is not harmless. An error analysis of commit-based memory for code localisation found that irrelevant memory can pollute an agent's reasoning and make results worse than having no memory, especially in repositories with sparse histories (Wang, Xu, et al., 2026).

**Knowledge that code cannot show.** Jansen and Bosch (2005) argued that design decisions are embedded implicitly in software and have no first-class representation, and they named the loss of knowledge about why an architecture is as it is "knowledge vaporization", identifying it as a partial cause of expensive change and decay. Recent empirical work gives this idea detail. Interviews and two surveys by Al Safwan et al. (2022) found that developers need the rationale of commits for several tasks, decomposed that rationale into 15 components, each needed, found and recorded differently, and identified factors that lead developers to give up searching for it. Knowledge is also lost when people leave: interviews with 27 developers and managers at three companies produced 20 observations on turnover-induced knowledge loss, and they showed that mitigation has to be tailored to its context (Robillard, 2021).

The obvious place to look for reasons is the commit history, but the evidence on how well it serves is divided. Tian et al. (2022) examined almost 1,600 commit messages from five highly active open-source projects and judged about 44% to need improvement. Messages lacking the reason for the change averaged 28%, around twice the 12% lacking a description of it. In contrast, Dhaouadi et al. (2024) found that 98.9% of commits to the Linux kernel's out-of-memory killer contained rationale. The conflict is best explained by scope, since the second study covers one component of a project with an unusually demanding review culture, and it cannot be taken as typical. Sun et al. (2026) report in a preprint that across 63 commits from five Java projects no single type of artefact consistently captured all components of rationale: commit messages and pull requests mostly stated the goal, while the need and the alternatives appeared more often in issues and pull requests. Their language model approach to recovering rationale reached 93.2% recall but 51.4% precision, which suggests that recovering reasons after the fact remains unreliable. The recognised alternative is to write reasons down deliberately, as architecture decision records, but adoption is low and about half of the GitHub repositories that use them hold only one to five records (Buchgeher et al., 2023). Recording reasons is therefore valuable, but it cannot be assumed to be a habit.

**Ownership of notes.** Who owns the memory matters as much as what it contains. Kleppmann et al. (2019) set out the ideals of local-first software, among them longevity, privacy and user control, and they showed through prototypes that such software is feasible while also finding that large histories raise performance and storage problems. Obsidian follows a similar path: notes are plain text Markdown files in a local folder, and other tools can edit them (Obsidian, 2025). A case study of industry researchers using Obsidian found that the way people plan to retrieve knowledge shapes how they organise their notes (Ferreira et al., 2025), which suggests that retrieval and note-taking are best designed together. It is a short paper on one research lab, so it indicates a direction and does not prove a general rule. The relevant challenge is that memory systems for language models generally hold their memory in a form that the system itself writes and manages, so that the person cannot readily read it, correct it or take it elsewhere.

## 2.3 Related Works

**Alignment with Objective ii:** To study how existing memory and code retrieval systems have given language models knowledge of a project.

The systems below are grouped from general agent memory, through code structure and memory for coding agents, to the evidence on whether such systems help. Each is described and then evaluated for its provenance, its method and the value of its evidence.

### 2.3.1 MemGPT, Generative Agents and Mem0: Memory for Language Model Agents

- **Description:** MemGPT manages memory tiers on the model of an operating system so that an agent can work beyond its context window (Packer et al., 2023). Generative Agents store experiences as natural language and synthesise them into reflections for planning (Park et al., 2023). Mem0 extracts, consolidates and retrieves key facts from ongoing conversations (Chhikara et al., 2025).
- **Technology:** Virtual context management with interrupts in MemGPT; a memory stream with retrieval and reflection, demonstrated with 25 agents, in Generative Agents; and fact extraction with an optional graph memory in Mem0, for which the authors report a 26% relative improvement over OpenAI's memory on LoCoMo, 91% lower p95 latency and over 90% lower token cost than using the full context.
- **Gaps:** (a) they are aimed mainly at conversation and social behaviour and were not designed around a codebase; (b) the memory is written by the model and not by a person; (c) privacy on one machine is not a stated aim.

**Critical evaluation.** Only Generative Agents has been peer-reviewed, and its ablation study measures believability and not task success. MemGPT and Mem0 are preprints evaluated by their own authors. Mem0 was also one of the four systems tested on coding work by Fan et al. (2026), where 11 of the 12 pairings of solver and memory system failed to beat having no memory (Section 2.3.11).

### 2.3.2 HippoRAG: Graph-Based Associative Retrieval

- **Description:** A retrieval framework modelled on human long-term memory, in which passages are linked through a knowledge graph, so that retrieval can follow associations across documents (Gutiérrez et al., 2024).
- **Technology:** A language model extracts a knowledge graph, and Personalized PageRank spreads activation over it. The authors report up to 20% better performance than other retrieval methods on multi-hop question answering, with single-step retrieval 10 to 30 times cheaper and 6 to 13 times faster than iterative retrieval.
- **Gaps:** (a) it is evaluated on general question answering and not on code; (b) it builds its graph by calling a language model during indexing; (c) its links are inferred by a model and not stated by an author.

**Critical evaluation.** The paper is peer-reviewed (NeurIPS 2024) and uses public question answering sets, but the comparison is made by the authors of the method. Its value here is conceptual: it is strong evidence that following associations can answer questions that similarity search alone cannot, which is the assumption behind link-following.

### 2.3.3 Aider Repository Map

- **Description:** A coding assistant that sends the model a concise map of a repository, naming files and their key symbols with signatures (Aider, 2023).
- **Technology:** Tree-sitter finds where symbols are defined and referenced, files become nodes in a dependency graph, and a graph ranking algorithm selects the most referenced identifiers to fit a budget that defaults to 1,000 tokens.
- **Gaps:** (a) the map holds structure and no reasons; (b) privacy depends entirely on the model chosen; (c) no evaluation is given.

**Critical evaluation.** The source is the project's own documentation and is not peer-reviewed, so the design is persuasive as engineering but its effect is unmeasured. Its enduring contribution is the idea of fitting a representation of a repository into an explicit budget, which is the same constraint that this study imposes on every memory condition.

### 2.3.4 RepoGraph: Repository-Level Code Graph

- **Description:** A plug-in module that manages a repository-level structure and gives AI software engineering systems a map of the code (Ouyang et al., 2025).
- **Technology:** A graph of the repository is supplied to an existing agent or pipeline. Added to four methods on SWE-bench, it improved all four, and the authors also tested it on CrossCodeEval.
- **Gaps:** (a) the graph contains code only; (b) it represents structure and not knowledge learned about a project over time; (c) privacy is left to the host system.

**Critical evaluation.** RepoGraph is peer-reviewed (ICLR 2025) and its plug-in design is a sound method, because it tests one change against four existing systems. However, the evaluation is carried out by the authors and on issue resolution alone, so it shows that structure helps locate code but does not address whether a project's history of decisions is respected.

### 2.3.5 GraphCodeAgent: Dual Graph Retrieval

- **Description:** An agent for repository-level code generation that retrieves both explicit and implicit context code by reasoning across two linked graphs (Li et al., 2025).
- **Technology:** A Requirement Graph holds relations among requirements, a Structural-Semantic Code Graph holds repository dependencies, and a language model agent reasons over multiple hops of them. It was tested with three language models on DevEval and CoderEval.
- **Gaps:** (a) requirements appear as statements of what should be done and not as a record of why choices were made; (b) the retrieval is driven by the model, which makes it harder to repeat and audit; (c) privacy is not addressed.

**Critical evaluation.** This work is a preprint, first posted under the title CodeRAG, and evaluated by its authors, and its abstract reports significant gains without scores. It is nevertheless valuable as the closest published parallel to the idea of connecting documents about intent with code, since its links run from requirements to code.

### 2.3.6 LocAgent: Graph-Guided Code Localisation

- **Description:** Agents that locate the code to change for a given issue by searching a graph of the codebase (Chen et al., 2025).
- **Technology:** Codebases are parsed into directed heterogeneous graphs of files, classes and functions, with imports, invocations and inheritance as edges, and agents reason over several hops. The authors report up to 92.7% accuracy at file level and a 12% improvement in Pass@10 for downstream issue resolution.
- **Gaps:** (a) only code relations are represented; (b) the highest results depend on fine-tuning for the task; (c) it treats each task from the start and retains nothing from one task to the next.

**Critical evaluation.** LocAgent is peer-reviewed (ACL 2025), and it is notable for reporting results on a model that can be self-hosted. The evidence is the authors' own and comes from one kind of task, but it supports the specific claim tested in this study, that following code relations can reach the files a fix must change.

### 2.3.7 Repository Memory for Code Localisation

- **Description:** A method of giving localisation agents a long-term memory of a repository by mining its commit history (Wang, Xu, et al., 2026).
- **Technology:** Tools let an agent query the 7,000 commits before an issue and their linked issues, together with summaries of functionality in the code that changes often. Added to LocAgent, the memory significantly improved results on SWE-bench-Verified and SWE-bench-Live, using GPT-4o as the model.
- **Gaps:** (a) what it can know of reasons is limited to what commits record, which Section 2.2.2 showed to be incomplete; (b) repositories with sparse histories can do worse than with no memory; (c) the reported runs use a cloud model.

**Critical evaluation.** The paper is peer-reviewed (ICLR 2026) and is unusually candid in its error analysis, although that analysis is described as small in scale. It is the strongest evidence reviewed that accumulated project history helps agents, and it stands against the more negative results in Section 2.3.11, in part because it measures finding the right file and not completing a task.

### 2.3.8 Codebase-Memory

- **Description:** The closest system built on a code graph, which parses a project into a persistent graph and serves it to language models through the Model Context Protocol (Vogel et al., 2026).
- **Technology:** Tree-sitter parses 66 languages into a single SQLite file, 14 tools are exposed, and only changed files are re-indexed. Across 31 repositories it scored 83% on answer quality against 92% for a file-reading agent, while using about ten times fewer tokens and 2.1 times fewer tool calls.
- **Gaps:** (a) the graph captures static structure only; (b) although a tool for architecture decisions is listed, the paper does not describe storing rationale; (c) comparison with embedding-based retrieval is left to future work.

**Critical evaluation.** The method is openly limited: the paper states that responses were graded by the first author, with one repository per language and a single model, so the figures should be read as indicative. The result is informative and balanced, because the system saved a great deal of cost and lost some quality, and the authors report both.

### 2.3.9 The Two codemem Projects

- **Description:** Two unrelated open-source projects share this name. One captures typed memories from coding agent sessions, including bug fixes, decisions and discoveries (kunickiaj, 2026). The other is a Rust engine that combines a code graph with memories and records files read, edits and decisions (Cogniplex, 2026).
- **Technology:** The first stores memories in local SQLite and retrieves them with FTS5 BM25 and sqlite-vec semantic search, merged and re-ranked. The second indexes 14 languages with Tree-sitter, adds commits to the graph, scores results on nine components including vector similarity, graph strength and BM25, uses a local embedding model by default, and exposes 32 tools.
- **Gaps:** (a) memories are derived mostly from agent activity, and neither project centres on a vault of notes written by a person; (b) the first project's observer step sends captured context to the configured model provider, so local storage does not mean local processing; (c) neither has a peer-reviewed evaluation.

**Critical evaluation.** These are open-source projects described by their authors. The first reports no evaluation, and the second reports 91.64% on LoCoMo and 70% on LongMemEval as self-reported figures that have not been replicated. Their value is that they show the retrieval design chosen for Burrow, namely words and meaning over local SQLite, to be established practice, so that any contribution of this study must lie elsewhere.

### 2.3.10 SIx Harness: Memory in Long-Running Practice

- **Description:** An open-source memory infrastructure reported from a months-long project with a single continuous coding agent session driving a codebase of 633,000 lines (Helwig, 2026).
- **Technology:** Per-project memory with hybrid lexical and vector retrieval over local SQLite, precision-gated injection of context, anti-recurrence stores for decisions and dead ends, and a health gate and telemetry for the memory itself.
- **Gaps:** (a) the author states that it is a single case with no control arm and self-reported data; (b) the memory is local, but the agent it serves is a cloud service; (c) it measures reliability of the memory subsystem and not improved outcomes.

**Critical evaluation.** This is a practitioner's preprint with a limited evidential weight, and the author is frank about that. Its value lies in documenting the need that motivates this study, that dead ends and decisions must be kept to prevent a project repeating them, and in publishing an ablation protocol that others could run.

### 2.3.11 VibeMemBench and MemoryArena: Benchmark Evidence

- **Description:** VibeMemBench tests whether memory improves executable coding success on 111 targets from 90 repositories, with 3,634 history trajectories (Fan et al., 2026). MemoryArena tests agents on human-crafted tasks with interdependent subtasks across sessions (He et al., 2026).
- **Technology:** VibeMemBench judges success by executable tests. Directly injecting verified experience raised task resolution by 1.1 to 4.5 percentage points on four of five solvers, but when Mem0, SimpleMem, MemoryOS and A-MEM built and retrieved experience from the same history, 11 of 12 pairings of solver and memory system failed to beat the memory-off baseline. MemoryArena covers web navigation, preference-constrained planning, progressive search and sequential formal reasoning.
- **Gaps:** (a) VibeMemBench is limited to experience gathered from past agent trajectories and does not test notes written by a person; (b) most of its transfer gains have confidence intervals that cross zero, and memory-side cost is not measured; (c) MemoryArena does not concern code.

**Critical evaluation.** VibeMemBench tests existing systems and not a new system of its own, and it reports its threats plainly, including optimistic target selection and a Python-heavy sample, which makes it the most objective evidence in this review, although it remains a preprint. MemoryArena, which is reported as an ICML 2026 paper, finds that agents that nearly saturate benchmarks such as LoCoMo perform poorly once memory must be used in later tasks, which casts doubt on the self-reported LoCoMo scores in Sections 2.3.1 and 2.3.9.

### 2.3.12 Better Call Grep and Is Grep All You Need?: Evidence for Plain Lexical Search

- **Description:** Two studies ask how far simple word search can go before more complex retrieval is required (Wang, Wang, et al., 2026; Sen et al., 2026).
- **Technology:** In the first, a language model generates ripgrep commands for repository-level code completion. This baseline performs comparably to graph-based methods, and adding identifier-weighted re-ranking and deduplication gave a 7.04% to 15.58% relative improvement in exact match over the best baseline on CrossCodeEval. The second compares grep with vector retrieval on 116 LongMemEval questions across a custom harness and three commercial command-line agents.
- **Gaps:** (a) index-free search cannot find code or notes whose words differ from the query; (b) the first study reports weakness on noisy keywords and fragmented context; (c) the second study uses conversation data and not code, and its scores depend strongly on the harness.

**Critical evaluation.** This work is contrary evidence that any study of graph or link-based retrieval must face. The first is reported in its arXiv record as an ISSTA 2026 paper and the second is a preprint, and both are evaluated by their authors, but they set a demanding baseline, since a system that follows links has to beat plain search and not merely beat nothing.

### 2.3.13 Repository Context Files

- **Description:** Files such as AGENTS.md, placed in a repository to give coding agents standing instructions and an overview of the project (Gloaguen et al., 2026; Lulla et al., 2026).
- **Technology:** Plain text read automatically by the agent. Gloaguen et al. (2026) used SWE-bench tasks with generated files and a new set of issues from repositories with committed files. Lulla et al. (2026) ran agents with and without a file on 124 pull requests across 10 repositories.
- **Gaps:** (a) the whole file is read every time, whether relevant or not; (b) neither study shows better task success; (c) the files give instructions and are not designed to hold a project's history of decisions.

**Critical evaluation.** The two studies appear to conflict, because Gloaguen et al. (2026) found that the files generally did not improve task success and raised inference cost by over 20%, while Lulla et al. (2026) found that they reduced median runtime by 28.64% and output tokens by 16.58%. The conflict is partly one of measure, cost per run against time per run, and both are preprints from independent groups who did not build the tools tested, so the most defensible reading is that the benefit is to efficiency when it exists. Gloaguen et al. also found the files useful for describing non-standard practices, and repository overviews not useful, which suggests that what a project cannot show on its surface is what is worth writing down.

### 2.3.14 Risks of Retrieved Content

- **Description:** Text retrieved into a prompt can act as an instruction. Greshake et al. (2023) demonstrated indirect prompt injection against real systems by planting prompts in content likely to be retrieved. The Model Context Protocol, through which tools expose data to language models, sets out security principles for such access (Model Context Protocol, 2026).
- **Technology:** Greshake et al. (2023) attacked Bing's GPT-4 chat, code completion engines and synthetic applications, showing theft of data and control of API calls. The protocol uses JSON-RPC 2.0 between hosts, clients and servers, requires user consent for data access and tool use, and treats tool descriptions as untrusted unless the server is trusted.
- **Gaps:** (a) effective mitigations for injection were lacking at the time of the study; (b) the specification notes that the protocol cannot enforce its principles itself, leaving this to each implementation.

**Critical evaluation.** Greshake et al. (2023) is a peer-reviewed security study based on working demonstrations and is persuasive. It means that any system that reads a person's files and passes them to a model has to treat those files as data, and that a memory is also an attack surface.

### 2.3.15 Generative AI in Place of Human Participants

- **Description:** Agnew et al. (2024) reviewed proposals to replace human participants with generative AI. Gerosa et al. (2024) examined whether AI can stand in for human subjects in software engineering research.
- **Technology:** A scoping review in the first and a vision paper on personas, synthetic qualitative data and simulated behaviour in the second.
- **Gaps:** (a) neither offers an empirical procedure for validating simulated agents; (b) the guidance is about claims concerning people and does not address measuring agent behaviour as an outcome in its own right.

**Critical evaluation.** Agnew et al. (2024) argue, in a peer-reviewed CHI paper, that such substitution conflicts with the values of representation, inclusion and understanding, and Gerosa et al. conclude that AI may scale data collection but cannot fully replace people. Both bear directly on this study, which uses simulated developer agents: the agents' behaviour may be measured and reported as agent behaviour, and nothing may be concluded from it about human usability.

### 2.3.16 Comparison of Related Systems

Table 2.1 compares the reviewed systems on what they store, on whether they can be private on one machine, on whether the memory is written by a person, and on how they were evaluated. Table 2.2 sets out their main strengths and critical gaps.

!tab Table 2.1: Comparison of related systems
!widths 1.5,1.5,1.2,1,1.3
| System | What it stores | Private on one machine | Written by a person | Evaluation |
| MemGPT | Conversation and archival memory | Not its focus | No | Own tests, preprint |
| Mem0 | Facts from conversations | Not its focus | No | LoCoMo, preprint |
| HippoRAG | Graph of passages | Not its focus | No | Question answering sets, peer-reviewed |
| Aider repository map | Code symbols, on request | Depends on chosen model | No | None given |
| RepoGraph | Code structure | Depends on host system | No | SWE-bench, peer-reviewed |
| GraphCodeAgent | Requirements and code graphs | Not its focus | No | DevEval and CoderEval, preprint |
| LocAgent | Code graph | Possible with self-hosted model | No | Authors' localisation tests, peer-reviewed |
| Repository Memory | Commits and code summaries | Not its focus | Commits only | SWE-bench variants, peer-reviewed |
| Codebase-Memory | Code structure in SQLite | Tool yes; client varies | No | 31 repositories, preprint |
| codemem (kunickiaj) | Memories from agent sessions | Sends context to a provider | Mostly no | None given |
| codemem (Cogniplex) | Code graph and memories | Local model by default | Partly | Self-reported |
| SIx Harness | Decisions and dead ends | Memory yes; agent is cloud | Partly | Single case, preprint |
| Repository context files | Instructions and overview | Depends on agent | Yes | Two preprints, no gain in success |
| Burrow | Notes and linked code | Yes, with Ollama | Yes | Agent test and real bug fixes, Chapter 5 |

!tab Table 2.2: Comparative Analysis of Reviewed Systems
!widths 1.5,2.3,2.7
| System | Strengths | Critical Gaps |
| MemGPT, Generative Agents, Mem0 | Established memory designs; large cost savings reported | Conversation focus; memory written by the model |
| HippoRAG | Follows associations across documents | Not tested on code; indexing needs a model |
| Aider repository map | Explicit budget; simple and practical | Structure only; no evaluation |
| RepoGraph | Improved four existing methods | Code only; no lasting project knowledge |
| GraphCodeAgent | Connects requirements to code | Preprint; no record of reasons |
| LocAgent | Multi-hop code search; works with an open model | One task; relies on fine-tuning |
| Repository Memory | Mines real project history | Limited by what commits record; can harm sparse repositories |
| Codebase-Memory | Very low token use; candid limits | Static structure; author-graded |
| codemem projects | Local hybrid retrieval; capture of decisions | Agent-derived memory; no independent evaluation |
| SIx Harness | Anti-recurrence stores; reliability data | Single case; no control arm |
| VibeMemBench, MemoryArena | Executable or interdependent tasks; test existing systems | No notes written by a person; small effects |
| Better Call Grep, Is Grep All You Need? | Strong plain baselines at low cost | Miss text with different wording; harness-dependent |
| Repository context files | Written by people; simple to adopt | Always read in full; no gain in task success |

## 2.4 Gaps in Related Works

A critical synthesis of the systems reviewed in Section 2.3 and compared in Tables 2.1 and 2.2 reveals persistent limitations in how language models are given knowledge of a project. Together they define the need that this study addresses.

**1. The reasons behind code are not a first-class memory**

Code graphs hold structure. RepoGraph, LocAgent and Codebase-Memory (Sections 2.3.4, 2.3.6 and 2.3.8) represent what code does and how it connects, and Codebase-Memory captures static structure only, even though it lists a tool for decisions (Vogel et al., 2026). Agent memories such as those in Sections 2.3.1, 2.3.9 and 2.3.10 record what an agent happened to do. Repository Memory (Section 2.3.7) comes closest, and its knowledge of reasons is bounded by commit messages, of which a substantial share omit the reason (Tian et al., 2022). The difficulty is that the rationale identified as being lost by Jansen and Bosch (2005), and shown to be spread across artefacts by Sun et al. (2026), is not the central concern of any system in Table 2.1.

**2. The memory is not owned by the person**

Table 2.1 shows that in nearly all reviewed systems the memory is written by the system. Only repository context files (Section 2.3.13) are written by people, and they are read whole on every run and hold instructions more than history. Local-first ideals (Kleppmann et al., 2019) and the practice of keeping notes as plain files (Obsidian, 2025) are well established, but no system reviewed uses a vault of ordinary notes, written and owned by the person, in a form that survives the tool, as the memory that a language model reads. The observation by Ferreira et al. (2025) that retrieval shapes how notes are kept remains unexplored by memory systems for models.

**3. Privacy is rarely a property of the whole path**

Several tools are local in storage but not in processing, as Table 2.1 shows. The codemem project of Section 2.3.9 sends captured context to a provider (kunickiaj, 2026), and the SIx Harness of Section 2.3.10 keeps memory locally for an agent that runs in the cloud (Helwig, 2026). Others leave privacy to the host system or the chosen model (Sections 2.3.3 and 2.3.4). Given the concerns documented by Klemmer et al. (2024), a memory that is private only in part does not meet the need of a developer who may not send code to a third party. Where text is retrieved, the path also needs defending against the injection risks of Section 2.3.14.

**4. Fair comparison with simple baselines is uncommon**

Many of the results in Table 2.2 are the authors' own, and several are preprints. The strongest independent evidence is discouraging: 11 of 12 pairings of solver and memory system failed to beat no memory at all (Fan et al., 2026), and strong LoCoMo scores did not transfer to tasks that depend on earlier sessions (He et al., 2026). Plain word search is a demanding baseline (Section 2.3.12), yet few systems are compared with both no memory and plain search under an equal limit on what may be read. Codebase-Memory leaves its comparison with embedding search to future work (Vogel et al., 2026). Very few studies test whether a system can admit that an answer is not recorded, even though LongMemEval shows that abstention can be measured (Wu et al., 2025).

**5. Link-following has not been tested across notes and code together**

Evidence for following links exists separately for code (Sections 2.3.4 to 2.3.6) and for general documents (Section 2.3.2), and the evidence in Section 2.3.12 suggests that simple search may match it. No reviewed study walks links that connect notes written by a person to the code they describe, and tests that walk against plain search under the same limit.

**6. Small local models are seldom the subject**

Most evaluations reviewed rely on large models. Codebase-Memory used one cloud model (Vogel et al., 2026), Repository Memory used GPT-4o (Wang, Xu, et al., 2026), and VibeMemBench tested provider models such as deepseek-v4-pro and glm-5 and reports no results for models sized for a laptop (Fan et al., 2026). The capability limits set out in Section 2.2.2 mean that these results cannot be assumed to carry over to a model that fits on a laptop.

**Key Unmet Need:** No system reviewed combines a memory written and owned by the person (unlike the systems in Sections 2.3.1 and 2.3.9), processing that is private along the whole path (unlike Sections 2.3.9 and 2.3.10), retrieval that connects notes with code and can be inspected (unlike Sections 2.3.3 to 2.3.8), and an evaluation on small local models against no memory and plain search under equal limits (unlike most of Table 2.2). This is the gap the present study targets.

## 2.5 Conceptual Framework

### 2.5.1 Definition and Purpose

The conceptual framework for this study visually and theoretically outlines how a private memory of notes and linked code is expected to affect a local language model's work on a project. It integrates the variables, relationships and processes drawn from the literature in Sections 2.2 to 2.4, and it aligns with objectives iv and v by stating what was built and what was measured.

### 2.5.2 Research Focus

**Topic:** A private, on-device vault as lasting memory for local language models.

**Research question:** Does giving a local language model a vault of notes written by a person, with linked code, retrieved by search or by following links, help it keep working on the same project better than having no memory, when each condition may read the same amount of text?

### 2.5.3 Key Variables and Concepts

**Input variables.** Three inputs enter the system:

- The person's question or task, such as a request to explain a decision or to change a function.
- Markdown notes, written by a person and held as ordinary files in a vault.
- Linked code folders, read by the system and changed only when the person accepts a proposed change.

**Processing variables.** The condition being compared is the memory condition, and it takes one of three values:

- **None:** the model receives no excerpts from the vault.
- **Search:** excerpts are selected by word search with BM25 and by embedding similarity, merged with reciprocal rank fusion.
- **Walk:** excerpts are selected by search and then by following links from imports, name definitions and notes, for up to two hops.

Every condition is held to the same reading limit of 12,000 characters and uses the same local model, so that a difference in outcome can be attributed to the memory condition. The equal limit follows from the finding that more context is not necessarily better (Liu et al., 2024) and from the need to compare with plain baselines (Fan et al., 2026).

**Output variables.** The outcomes are:

- An answer that names the files and lines it used.
- Later tasks passed across a sequence of sessions.
- Earlier decisions kept and not undone.
- An honest statement when a reason was not recorded, following the abstention measure of Wu et al. (2025).
- Changed files reached, meaning whether retrieval arrives at the files a real fix altered.
- Index size and speed as a project grows.

### 2.5.4 Theoretical Foundation

The framework draws on two bodies of theory to explain the expected relationships. The system was not designed from them, and they are used here as explanation. The first is information foraging theory, which holds that people seeking information behave like animals foraging for food, following cues known as scent and weighing the expected value of a source against the cost of reaching it (Pirolli & Card, 1999). Lawrance et al. (2013) applied this to programmers. In a study of 10 professional programmers debugging a real open-source program, the programmers' verbalisations concerned scent-following far more often than hypotheses, and a model that considered scent predicted navigation more accurately than comparable models that did not. Foraging explains why links might help a model: an import or a note that names a function is a cue that leads onwards, and following it reaches material that shares no words with the question. It also explains the cost, since a reading limit makes every link followed compete with the excerpts it displaces.

The second is the account of design rationale and knowledge loss. Jansen and Bosch (2005) explain why reasons vanish when decisions have no first-class representation, and recent studies of rationale show that this knowledge is scattered and incomplete (Al Safwan et al., 2022; Sun et al., 2026). This account explains why a note written by a person may hold what no amount of code retrieval can recover, and equally why a model should state plainly that a reason was not recorded instead of inventing one.

### 2.5.5 Visual Representation

Figure 2.1 presents the conceptual framework of the study. It shows the inputs, the three memory conditions held to one reading limit and one local model, and the outputs measured.

!fig figures/framework.png | Figure 2.1: Conceptual framework of the study. | 6.1

### 2.5.6 Relationships Between Variables

The framework set out the following relationships, each of which was a proposition tested in Chapter 5 and not a finding:

- Providing excerpts from notes and code (Processing) is expected to raise the later tasks passed and the earlier decisions kept (Output), compared with providing none.
- Notes that record reasons (Input) are expected to improve answers to questions about why, which code alone cannot answer (Output).
- Following links (Processing) is expected to reach changed files that word and embedding search miss (Output), at the cost of using part of the same reading limit.
- The absence of a recorded reason (Input), combined with grounded retrieval (Processing), is expected to produce a statement that the reason was not recorded instead of an invented reason (Output).
- The number of files in a vault (Input) is expected to affect index size and speed (Output) without affecting the fixed reading limit.

### 2.5.7 Flexibility and Refinement

The framework was treated as provisional. The testing reported in Chapter 5 led to no change in its variables or relationships, although it showed which of the relationships could not be supported.

### 2.5.8 Worked Example Applied to Burrow

The following narrative flow illustrates the framework; it is an illustration and not a result.

i) A developer asks: "Why does the payment client stop after three retries?" (Input).
ii) Burrow retrieves excerpts up to the reading limit. In search, the words "retry" and "limit" find a note in the vault. In walk, a link from that note leads to the function it names (Processing).
iii) If a note records the reason, for instance that the payment provider blocks accounts after a fourth attempt, the local model gives that reason and names the note and the lines of code used (Output).
iv) If no note records the reason, the model answers from the code what the limit is, and states that the reason is not recorded, without inventing one (Output).
v) The developer may write the reason down as a note, after which it is available to every later session (Iteration).

### 2.5.9 Key Considerations

**Alignment with objective iv (design and develop).** The inputs and the three memory conditions define what Burrow must provide: a vault of notes, linked code folders and retrieval that can be set to none, search or walk under one limit, as well as the Mac app, terminal version and MCP server through which these are reached.

**Alignment with objective v (test and validate).** The output variables correspond to the tests: the functions of the system, the effect on simulated developer agents across sessions, the ability to reach the code a real fix changed, and size and speed as a project grows. The conditions and the equal limit provide the comparison with no memory and with plain search that Section 2.4 found to be uncommon.
