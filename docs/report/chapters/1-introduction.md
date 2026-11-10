# Chapter 1:  Introduction

## 1.1 Background Information

Nearly half of the developers surveyed by Stack Overflow in 2025 used an AI tool every day, and most of those who answered on AI agents were worried about the security of their data. In that survey, 47.1% of respondents reported using AI tools daily, while 81.4% agreed at least somewhat that they worry about data security and privacy when using AI agents (Stack Overflow, 2025). In interviews with software engineers, team leads and security testers, leaking sensitive data to third-party assistants was the main concern named by most participants, and a few reported that their companies had banned such tools for privacy reasons (Klemmer et al., 2024).

The development of the field explains this tension. Code assistants grew up as cloud services because capable language models needed data-centre hardware, which meant that a developer's code had to leave the machine in order to be read. Two later developments changed what is possible. Models became small enough to run on a laptop, including the smaller members of the Qwen3 family, which range upward from 0.6 billion parameters (Yang et al., 2025). Runtimes such as Ollama then made such models easy to operate, and its documentation states that prompts and data from local runs are not seen by its team (Ollama, 2026b). At the same time, retrieval-augmented generation became a standard way of supplying a model with knowledge it was not trained on (Gao et al., 2023), and memory systems were proposed to carry knowledge from one session to the next (Packer et al., 2023; Chhikara et al., 2025).

A local model solves the privacy problem and leaves another untouched: it has no memory of the project. Each session begins from nothing, and the model's context window is limited. Giving a model a long input is not a full remedy, because models use information in the middle of a long context less well than information at its start or end (Liu et al., 2024). A further difficulty is that much of what a developer needs was never in the code. Jansen and Bosch (2005) named the loss of knowledge about why a system is built as it is "knowledge vaporization", and identified it as a partial cause of expensive change and decay.

Existing work leaves several gaps, which are developed in Section 2.4. Code graphs and repository maps capture the structure of code but not the reasons behind it (Ouyang et al., 2025; Vogel et al., 2026). Memory tools for coding agents capture session activity, often sending it to a model provider. Evidence that any of these help is also thin: when existing memory systems built and retrieved experience in one recent benchmark, 11 of 12 pairings of solver and memory system failed to beat having no memory at all (Fan et al., 2026). Closing these gaps matters practically, because a developer who cannot upload code otherwise has to re-explain the project in every session or go without AI help, and it matters scientifically, because claims about memory are only useful when tested against simple baselines.

Burrow was built to address this. It is a private Mac application in which a folder of ordinary Markdown notes forms a vault, as in the note-taking tool Obsidian, and code folders can be linked in without being changed. When a question is asked, Burrow finds the few pieces of notes and code that bear on it and passes only those to a local model, which names the files it used. Its retrieval can follow links drawn from imports, name definitions and notes.

The study was guided by the following hypothesis. Within the same upper reading limit, following links reaches more of the files that a real fix changed than plain search does; and a local model given such memory finishes more later tasks and breaks fewer earlier decisions than it does with no memory or with plain search, while the index stays small and fast enough to use as a project grows.

## 1.2 Problem Statement

A developer should be able to ask an AI about their whole project, session after session, including why it was built the way it was, without giving the project away. In reality, cloud assistants require sending code that a developer may not be permitted to share, and 81.4% of surveyed developers are concerned about the security and privacy of their data when using AI agents (Stack Overflow, 2025). A local model avoids this, yet it forgets the project at the end of every session, and lack of project-size context is itself among the reasons developers give for not using assistants (Sergeyuk et al., 2025). Existing memory tools store code structure or session activity, and when such systems built and retrieved experience in one recent benchmark, 11 of 12 pairings failed to beat having no memory (Fan et al., 2026). The consequence is that a developer must re-explain a project repeatedly or do without help, and a local model can repeat a fix that was already rejected. This study developed a private vault of notes and linked code for local models and tested, against no memory and plain search, whether it helps them keep working on the same project.

## 1.3 Research Objectives

### 1.3.1 General Objective

To develop and evaluate a private, on-device vault that gives local language models a lasting memory of a person's notes and software projects.

### 1.3.2 Specific Objectives

i) To analyse the current state of local language model use on private software projects, and the challenges involved.
ii) To study how existing memory and code retrieval systems have given language models knowledge of a project.
iii) To review the challenges and gaps remaining in those systems.
iv) To design and develop Burrow, a private vault with retrieval for local models, as a Mac app, a terminal version and a Model Context Protocol server.
v) To test and validate Burrow by the project's final defence on 23 November 2026, in four respects: (a) each of its functions, (b) its effect on simulated developer agents working across sessions, (c) its ability to reach the code a real fix changed, and (d) its size and speed as a project grows.

## 1.4 Research Questions

i) What is the current state of local language model use on private software projects, and what are its challenges?
ii) How have existing systems given language models knowledge of a project?
iii) What challenges and gaps remain in those systems?
iv) How can a private vault with retrieval for local models be designed and developed?
v) How well does Burrow perform when tested and validated, specifically:

- **v(a).** Does each function of Burrow work as required?
- **v(b).** With Burrow, do simulated developer agents finish more later tasks and break fewer earlier decisions than with no memory or with plain search?
- **v(c).** Does following links reach the files a real fix changed better than plain search does?
- **v(d).** Does Burrow stay small and fast as a project grows?

Questions i to iii are answered from the literature in Chapter 2, question iv in Chapters 4 and 5, and question v in Section 5.7.

## 1.5 Justification

**Current knowledge.** Developers are concerned about sending code to third parties (Klemmer et al., 2024). Retrieval lets a model use knowledge it was not trained on (Gao et al., 2023), and code graphs can help AI software engineering systems (Ouyang et al., 2025; Vogel et al., 2026).

**Identified gaps.** What is missing is a tool that holds the reasons behind code in a form that the developer owns, and that is evaluated openly against simple baselines. Memory systems for coding agents have seldom beaten no memory when they built their own memory (Fan et al., 2026), and none of the systems reviewed uses a vault of notes written and owned by the person.

**The problem this causes.** A developer who must keep code private has to re-explain the project in every session or go without AI help, and a local model can repeat a fix that was already rejected. One search for studies specific to Kenyan or African developers found none, so the argument here rests on international evidence.

**This study's contribution.** Burrow contributes a private vault in plain files, retrieval that can be inspected, and a test harness that holds each memory condition to the same reading limit.

In summary, this work is intended to help developers who work with code they cannot upload, and anyone who wants a local model to read their notes, by giving a local model a private and checkable memory, while advancing research on how memory for language models should be evaluated.

## 1.6 Scope

This study focused on a private memory vault for local language models, within the boundaries below.

- **Technical scope:** a Swift application for macOS using SQLite and Ollama, with a Mac app, a terminal version and a Model Context Protocol server.
- **Data scope:** a person's own Markdown notes and code folders; synthetic test projects written for the evaluation; and four public open-source repositories with 101 real bug fixes from SWE-bench.
- **Functional scope:** writing and linking notes, linking code folders, searching, viewing a graph, asking questions, and proposing changes that a person must accept.
- **Time scope:** the project ran to November 2026 in the phases below, and is charted in Appendix 1.

i) Phase 1: literature review and proposal, May to July 2026.
ii) Phase 2: analysis and design, July and August 2026.
iii) Phase 3: an earlier prototype named CAMR, September to November 2026.
iv) Phase 4: Burrow, built and tested on 9 and 10 November 2026, with Chapters 1 to 5 of this report rewritten for it.
v) Phase 5: evaluation of the frozen version, 10 November 2026.
vi) Phase 6: report and final defence, to 23 November 2026.

**Exclusions.** This study did not address live previews of running code, operating systems other than macOS, or the training or fine-tuning of language models.

## 1.7 Limitations and Delimitations

**Delimitations** are the boundaries set on purpose.

- The study covers one operating system, macOS, because a single platform allowed the app to follow that platform's conventions in the time available.
- Models available through Ollama were used, because local operation is the premise of the study.
- Evaluation concentrated on software tasks, although the vault can hold any notes, because hidden tests give an objective measure on software tasks.
- Cloud models were excluded from the evaluation, other than one trial through the Model Context Protocol, because the study concerns local models.

**Limitations** are the factors beyond the study's control.

- Human participants could not be obtained in the time available, because the classmates who might have taken part were not available, so the agent evaluation uses simulated developer agents, and no claim is made about usability or about human users.
- Only one development machine was available, so timings and the installation procedure apply to that machine.
- The small local models may fail tasks even when given the right context, which limits how much any memory system can show.
