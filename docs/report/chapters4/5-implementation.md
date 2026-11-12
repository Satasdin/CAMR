# Chapter 5:  System Implementation, Testing and Evaluation

## 5.1 Introduction

This chapter presents how the design of Chapter 4 was implemented, tested, and evaluated, and it addresses the third, fourth, and fifth specific objectives. The study followed the artificial intelligence route of the data-to-model workflow. Section 5.2 states the implementation environment, Section 5.3 describes the dataset and its preparation, and Section 5.4 presents each part of the engine in the order of the architecture in Chapter 4. Section 5.5 evaluates the models, Section 5.6 reports the system tests, and Sections 5.7 and 5.8 give the version control evidence and the declaration of AI-assisted tools. Section 5.9 discusses the results against each specific objective and research question, and states their limitations. Every results table and chart was produced by a script from saved answers, and the scripts are in the repository beside the results.

## 5.2 Implementation Environment

Burrow is meant for a consumer computer that can run a local model service. It was developed and tested on one laptop of that kind, and it is published for download from a public landing page. The models ran in Ollama on the same machine, and the cloud model was called only by the evaluation harness.

### 5.2.1 Hardware and Deployment Environment

Table 5.1 states what the system needs and the machine on which it was tested. That was the only configuration tested, so other computers and operating systems are not claimed.

!tab Table 5.1: Hardware and deployment environment
!widths 1.0,2.0,2.2,1.1
| Item | Tested specification | Purpose and justification | Evidence |
| Computer | A consumer laptop with 24 GB of shared memory (tested on an Apple MacBook Pro, M5 Pro chip) | Runs the engine, the index and the local models together, which is the on-device setting the study is about | burrow fit output, Figure 5.5 |
| Storage | Internal SSD | The index is one database file beside the vault, and the vectors are one file mapped into memory | NFR-05 |
| Graphics | The chip's own graphics processor, no separate card | Used by Ollama to run the models | Ollama (2026) |
| Network | Needed only to download models and to call the cloud model during evaluation | The engine itself works offline | NFR-01 |

### 5.2.2 Software, Services and Configuration

Table 5.2 lists the software and the models with the versions that were tested.

!tab Table 5.2: Software, models and services
!widths 1.7,1.8,2.8
| Software | Tested version | Role and reason |
| macOS | 27.2 | Operating system of the tested computer; the package requires version 14 or later |
| Swift | 6.4.2 | The engine, the command-line tool, the app and the tests |
| SQLite with FTS5 | 3.54.0 | The embedded index: word search, vectors and links |
| Ollama | 0.40.14 | Runs the frozen local models on the device |
| Gemma 4 12B | gemma4:12b, 7.7 GB | The main on-device model |
| Qwen3.5 4B | qwen3.5:4b, 4.0 GB | The small on-device model |
| Qwen3 Embedding 0.6B | qwen3-embedding:0.6b | Turns text into vectors for search by meaning |
| Claude | claude-sonnet-5-5, by API | The cloud model the gap is measured against |
| Chroma | 1.5.9 | The vector database baseline |
| LangChain | langchain-core 0.3.86 | Shows Burrow working inside a framework |
| Python | 3.9.6 | The evaluation harness and the charts |

The key for the cloud service was read from a private file outside the repository.

### 5.2.3 Deployment and Reproducibility

The release path of Section 4.4.5 is live. The landing page at https://satasdin.github.io/CAMR offers the desktop application and the one-command install from the release burrow-v1.1.0, for Apple silicon and macOS 14 or later. The application is not signed with Apple, so on first open after a browser download macOS requires the person to choose Open Anyway; installing it with the command avoids this step. The system can also be built from source. A person needs the Swift toolchain and Ollama, and pulls the two models with ollama pull gemma4:12b and ollama pull qwen3-embedding:0.6b. The command swift build -c release builds the command-line tool, and app/build.sh builds the desktop application. The command burrow index builds the index of a vault, and burrow fit measures the model once. A first question through burrow ask verifies that the installation works. The evaluation is repeated by following trials/gap/README.md in the repository. Everything runs locally except the two cloud set-ups, which need a paid key for the Claude service. No dataset in the study is restricted.

## 5.3 Dataset Description

### 5.3.1 Description of the Dataset

The evaluation used one vault of real documents and 170 questions. The material suited the objective because an on-device model cannot know it well: it is law specific to Kenya, software documentation dated 2026, and a private project. Table 5.3 describes it. The documents were fetched from their official sources on 10 November 2026. The private project is Burrow's own source code and decision log at an earlier tagged version, written days before the evaluation.

!tab Table 5.3: The evaluation vault and its questions
!widths 1.0,2.3,0.45,0.75,0.8,1.0
| Subject | Material | Files | One-fact questions | Several-fact questions | Reasoning problems |
| Kenyan law | Data Protection Act (Cap. 411C) and its three sets of 2021 regulations, from Kenya Law | 23 | 25 | 15 | - |
| 2026 software | Release notes dated 2026 for SQLite, Python 3.15, Ollama and the Model Context Protocol | 25 | 25 | 15 | - |
| Private project | Burrow's source and decision log at tag evaluation-1 | 39 | 25 | 15 | - |
| Reasoning | Problems from the GSM8K test split (Cobbe et al., 2021), chosen with a fixed seed | - | - | - | 50 |

The 120 knowledge questions are synthetic data: Claude Code agents wrote them from the documents, with an answer key for each. A several-fact question needs two passages from two different files. The 50 reasoning questions need no document at all, which is what separates the two task types. Table 3.1 shows two of the records.

### 5.3.2 Data Preparation and Partitioning

The documents were converted to Markdown and placed in one vault. Each file was cut into pieces of about 45 lines and at most 3,000 characters, and each piece was entered in the word index and given an embedding vector. A script checked every answer key against the quoted evidence and rejected any key that appeared in its own question.

The data was prepared so that nothing could leak. The vault holds the source documents only, and the questions and keys are kept in a separate folder that the engine never indexes. The engine's thresholds were set on separate development questions, written with Claude Code, although several concern the same subjects as scored questions. The evaluation plan records that the scored questions were not read during tuning, so they played the part of a held-out test set. The final program was built one minute before the first scored run.

## 5.4 System Implementation

The engine is one Swift library with four surfaces over it: a command-line tool, a desktop app, a terminal chat and a Model Context Protocol server. This section shows each part working, in the order of Figure 4.6 and Figure 4.7, and links each to its requirements.

### 5.4.1 The Vault and Its Index

The vault is an ordinary folder that the person chooses, which implements FR-01 and DR-01. Figure 5.1 shows the map of a vault in the desktop app. Each dot is a note or a file, each line is a link, and the colours are folders. This is the evaluation vault of Section 5.3. It holds 59 notes and 37 code files, joined by 290 links.

!fig figures/screens4/app-graph.png | Figure 5.1: The map of a vault in the desktop app, coloured by folder | 6.2

Figure 5.2 shows a note of the evaluation vault being edited. The note is a plain Markdown file, its properties are shown as fields above the text, and the panel on the right draws its neighbours and lists the notes that link to it.

!fig figures/screens4/app-note.png | Figure 5.2: A note in the desktop app, with its properties and links | 6.2

### 5.4.2 Decide

For every question the engine runs one fast search and reads its signal. It then decides whether the vault is needed and how to read it, which implements FR-04 and FR-05. Figure 5.3 shows a question about code on the command line. The engine followed the links between files, handed the model the skill for explaining code, and reported what it read.

!fig figures/screens2/console-engine.png | Figure 5.3: The engine answering a question about code and reporting its decision, the skill used, the files read and the citation check | 6.2

Candidates are ranked by their words and meaning together. Recency, taken from a note's date or the file's last change, and importance, taken from how many files link to it and whether it records a decision, then break ties between equally relevant files (decision D-67 in the repository).

Figure 5.4 shows the opposite decision. The question is a sum, so the engine left the vault out, because nothing in it was close enough, and gave the model the skill for working a calculation. The lines under the answer say so: nothing was read, and the model read 207 tokens.

!fig figures/screens4/console-sum.png | Figure 5.4: A sum answered with the vault left out, on the command line | 6.2

### 5.4.3 Fit

The engine measures a model once and keeps the result with the vault, which implements FR-06. Figure 5.5 shows a measurement of the main model and the list of skills the vault holds.

!fig figures/screens2/console-fit.png | Figure 5.5: Measuring a model once with burrow fit, and the skills in the vault | 6.2

For the scored runs Gemma 4 12B was measured at about 670 tokens a second and was shown 17,417 characters of the vault in a window of 16,384 tokens. The smaller model was shown 12,000 characters. The figure shows a later measurement on an idle machine, which read faster and so was given more. The fit depends on what else the machine is doing when it is taken.

### 5.4.4 Answer and Check

In the desktop app the answer comes from the program the person already uses, and the app shows what that program read, which implements IR-01. Figure 5.6 shows Gemma 4 12B in OpenCode answering two questions from the vault through the MCP server: a question about breach notification under Kenyan law, which it answered with the seventy-two hours of the regulations, and a question about the project's code. The conversation page lists each lookup in the model's own words and a card for every file it read, and each card opens its file.

!fig figures/screens4/app-session.png | Figure 5.6: A conversation Gemma 4 12B held with the vault through OpenCode, with each lookup and the files it read | 6.2

Figure 5.7 shows the Programs page, which answers the Sprint II request to see model activity. Each program that can use the vault is drawn as a line running into it, bright when the program has read from the vault that day and dashed when it is not set up. The page reads each program's own settings to say whether it starts Burrow on this vault. Pointing at a line shows that program's last question and the files it read most, and clicking it opens its conversations; below are the lookups of the day and the setup for each program.

!fig figures/screens4/app-programs.png | Figure 5.7: The programs that use the vault, with the files OpenCode read most today | 6.2

On the command line every file and line in the answer is compared with what the model was shown, and the model is asked once more if a citation was not among them, which implements FR-08. Figure 5.8 shows what happens when the excerpts do not hold the answer. The question is about Ugandan law, which the vault does not contain. The engine still searched, because the closest files are about data protection, and the model said that it did not know from what it was shown, while the lines below list the nine files it read.

!fig figures/screens4/console-miss.png | Figure 5.8: A question the excerpts could not answer, and the model saying so | 6.2

### 5.4.5 Skills and Learn

A skill is a Markdown file in the vault's Skills folder. Figure 5.9 shows one. The line beginning with the word when is what a question is matched against, and the numbered steps are what the model is given. A person can edit a skill or add a new one as an ordinary note.

!fig figures/screens2/console-skill.png | Figure 5.9: A skill as it is stored in the vault | 6.2

After a conversation the engine can propose up to three notes of what the person decided, which implements FR-09 and DR-03. In the terminal chat's /keep command, a note is offered only if its quote is found in the person's own words, and it is written only when the person accepts it. The app proposes notes without the quote check and writes each one only on Keep. The command burrow learn applies the quote check but does not ask, and over MCP consent rests with the client.

### 5.4.6 Serving Other Models and Tools

The engine is not tied to the model it hosts, which implements FR-10 and IR-03. Not every surface runs every step: the check with a retry runs only on the command line, the application warns about an unverified citation, and the terminal chat and the MCP server use a fixed budget of 12,000 characters rather than the fitted one. Figure 5.10 shows an outside client asking Burrow to prepare a task through the Model Context Protocol. Burrow returns its decision and the excerpts without calling a chat model.

!fig figures/screens2/console-mcp.png | Figure 5.10: An outside client calling the tool vault_prepare through the Model Context Protocol | 6.2

Figure 5.11 shows Burrow used as the retriever inside a LangChain pipeline, in the place where a vector database would normally sit.

!fig figures/screens2/console-langchain.png | Figure 5.11: Burrow as the retriever in a LangChain pipeline | 6.2

### 5.4.7 Workflows with a Model

Burrow is not used on its own. A person works in the program they already use, and that program reaches the vault through the Model Context Protocol server. The workflows below were run on 12 November 2026 on a copy of the evaluation vault, with Claude Code as the working program in Figures 5.12 to 5.14 and Qwen3 4B in llama.cpp in Figure 5.16; Figure 5.6 shows the same kind of session with Gemma 4 12B in OpenCode. Each figure is a frame of a screen recording made during the run, and the recordings are kept with the repository's demonstration material.

Connecting a program takes one command. Figure 5.12 shows the server added to Claude Code, which then reports it as connected. OpenCode, LM Studio and llama.cpp connect in the same way, and the Programs page of the app writes the setting for each (Figure 5.7).

!fig figures/workflow/connect.png | Figure 5.12: The vault connected to Claude Code through the Model Context Protocol | 6.2

In a working session the program, not the person, asks Burrow. In Figure 5.13 a question about the breach-notice deadline was put to Claude Code, shortened on screen to c, a command that runs Claude Code allowed to use only Burrow's tools. Claude Code searched the vault through Burrow, answered 72 hours with the file and line, and, as asked, kept the team's 48-hour target as a decision in the Ledger, citing the file it rests on. The lines below the answer show the commit as Burrow stored it.

!fig figures/workflow/session-one.png | Figure 5.13: A Claude Code session that fetched an answer through Burrow and kept a decision in the Ledger | 6.2

Figure 5.14 shows the memory fetched again. A new Claude Code session, with no chat history, was asked what had been decided. It found the decision through Burrow, gave it with its reason, and said which part of the reasoning the record did not hold.

!fig figures/workflow/session-two.png | Figure 5.14: A new session that recalled the decision from Burrow, with no chat history | 6.2

Figure 5.15 shows what Burrow turns a question into before any model reads it: short rules, then excerpts marked with their file and line numbers, which is why an answer can name the line it rests on. Finding the excerpts took 0.05 seconds in the same run.

!fig figures/workflow/what-the-model-reads.png | Figure 5.15: The text Burrow hands a model for a question: rules, then excerpts marked with file and line | 6.2

The last workflow addresses the time a local model spends reading before its first word. Burrow can keep that reading, the model's working memory for a set of files, on the disk and load it back for a later question. In Figure 5.16 the same question was put to Qwen3 4B twice. Read from the start, the model processed 2,773 tokens and began to answer after 1.66 seconds. With the saved working memory, Burrow loaded it in 0.09 seconds, the model read only the 20 tokens of the question, and the answer began after 0.18 seconds. Both answers were the same.

!fig figures/workflow/saved-cache.png | Figure 5.16: Time to the first word without and with the model's saved working memory | 6.2

### 5.4.8 Design Decisions Made During the Build

Several decisions were made as the work progressed, each for a stated reason. In the evaluation, the main model had 12 billion parameters, the largest that fit the 24 GB laptop with room for the vault; questions were curated from source documents that the models could not have memorised, because public question-answering benchmarks are likely to have been seen in training; each question was run once rather than timed over repeated runs; and the budget sweep and the ten-point reporting rule of Table 5.6 were added after the evaluation plan was set. In the build, five parts changed. After Evaluation 2, the desktop app's own question box was removed, because the vault is the memory and the chat belongs to the programs that connect to it; the app now shows what those programs read (Figures 5.6 and 5.7), and the engine's decision is shown on the command line and in the terminal chat. The memory became a vault of files that a person writes instead of a stream of notes from each interaction, because the Sprint II review asked for something a person can see and use. Recency and importance were therefore taken from the files themselves, and they were built after the engine was frozen for Evaluation 2, so its scores do not include them. The Check step was added during the study, because a small model's citations can be compared directly with what it was shown. The engine was also written in Swift in place of Python, so that it runs as one compiled program on the target platform.

## 5.5 Model Selection and Evaluation

### 5.5.1 Baselines and Set-ups

No model was trained or fine-tuned. The on-device models were selected because they are recent open-weight models sized for the laptop, and they were used as published. Local answers were generated at temperature 0 with a fixed seed, but repeated runs still differed: of 169 identical prompts run twice, 41 answers changed in wording and one changed in score. The cloud model does not accept a temperature setting.

The same 170 questions were put to six set-ups, which Table 5.4 lists. Set-ups 1 to 4 were run with Gemma 4 12B and again with Qwen3.5 4B. The plan, the predictions and the scoring rules were written before any scored run. The budget sweep, the reporting threshold in Table 5.6 and the coding trial reported with the further results in the repository were added after the plan, and the cloud model could not be run at temperature 0 as planned.

!tab Table 5.4: The six set-ups compared
!widths 0.4,1.9,4.0
| No. | Set-up | What the model is given |
| 1 | Model alone | The question only. This is the floor. |
| 2 | Plain retrieval | The best-ranked excerpts pasted in front of the question, 12,000 characters. This is Burrow as it was before the engine's steps were built. |
| 3 | Vector database (Chroma) | A standard vector database pipeline with the same embedding model and the same 12,000 characters. This is the baseline. |
| 4 | Burrow engine | The prompt prepared by the engine's steps, up to 17,417 characters on Gemma 4 12B and 12,000 on Qwen3.5 4B. This is the treatment. |
| 5 | Cloud model alone | The question only, sent to Claude. This is the ceiling. |
| 6 | Cloud model with Burrow | The prompt that the engine prepared, up to 24,000 characters, sent to Claude. |

### 5.5.2 Evaluation Metrics

Accuracy is the share of questions answered right, as Equation 5.1 states. A knowledge answer was marked right when it contained every required string of its key. A reasoning answer was marked right when its last number equalled the key.

!eq accuracy | Equation 5.1: Accuracy of a set-up

The fraction of the capability gap closed is Equation 3.1, where the floor is the on-device model alone and the ceiling is the cloud model, taken both with the same vault and alone. Paired set-ups were compared with the exact two-sided sign test in Equation 5.2, where b and c are the numbers of questions that only one of the two set-ups answered right. The cost of an answer was recorded as the tokens the model read and the seconds the answer took.

!eq sign | Equation 5.2: Exact two-sided sign test on paired answers

### 5.5.3 Results on the Main Model

Figure 5.17 and Table 5.5 give the answers right for the main model. Alone, Gemma 4 12B answered 9 of the 120 knowledge questions (8%, with a 95% Wilson interval of 4% to 14%). With the engine it answered 102 (85%, 78% to 90%). The cloud model alone answered 40 (33%, 26% to 42%), and 109 (91%, 84% to 95%) when it was given the same vault, prepared by the engine with a limit of 24,000 characters.

!fig figures/v2/chart-accuracy-main.png | Figure 5.17: Answers right by set-up and task type, Gemma 4 12B and the cloud model | 6.2

!include generated2/accuracy-gemma4-12b.md | Table 5.5

The reasoning column shows the opposite effect. Alone, the model solved 47 of 50 problems. With plain retrieval it solved 7: on 43 of the 50 it replied that it did not know from what it had been shown, as the retrieval prompt instructs when the excerpts lack the answer, so the size of this harm reflects that prompt as much as the excerpts. With the Chroma baseline, whose prompt has a similar rule, it solved 42. The engine left the vault out of all 50 and the model solved 48.

Table 5.6 gives the fraction of the gap closed against both ceilings. Against the cloud model given the same vault, which compares like with like, the engine closed 93% of the gap on knowledge with Gemma 4 12B and 83% with Qwen3.5 4B, where plain retrieval closed 85% and 88%. Against the cloud model alone the fraction passes 100%, reaching 300% for the engine on Gemma 4 12B, because the cloud model could not have seen most of this material; that figure shows a weak ceiling, not an engine three times better than the cloud. On reasoning questions the ceiling was only 2 questions above the floor on Gemma 4 12B and 3 on Qwen3.5 4B, so the fraction, 50% and 100%, swings on a single answer. By a rule added after the plan, Table 5.6 does not report a fraction when the gap is under ten points.

!include generated2/gap.md | Table 5.6 | 0.95,0.85,1.05,0.95,0.95,0.7,0.65,0.65

Table 5.7 gives the cost. The engine showed the main model more of the vault than plain retrieval did, about 6,100 tokens against 3,800, and an answer took 9.2 seconds against 8.3. The engine's own work before the model started took 0.06 seconds. The engine brought back every file holding the answer on 111 of 120 questions, against 102 for plain retrieval and 95 for Chroma.

!include generated2/cost.md | Table 5.7 | 1.15,1.5,0.8,0.8,0.9,1.15

### 5.5.4 Results on the Small Model

The smaller model gave a mixed result, shown in Figure 5.18. Alone, Qwen3.5 4B answered 6 of the 120 knowledge questions. With plain retrieval it answered 97, with the Chroma baseline 75, and with the engine 91. On knowledge the engine therefore did not improve on plain retrieval for this model (1 question gained and 7 lost, p = 0.070). On reasoning the pattern of the main model repeated more sharply: 46 of 50 alone, 9 with plain retrieval, 1 with the Chroma pipeline, and 49 with the engine. The repository's further results (https://github.com/Satasdin/CAMR/blob/burrow/docs/evaluation/further-results.md) give the full counts, the results by subject and every paired test.

!fig figures/v2/chart-accuracy-small.png | Figure 5.18: Answers right by set-up and task type, Qwen3.5 4B and the cloud model | 6.2

### 5.5.5 Ablation, Budget and Speed

Two parts of the engine were switched off in turn on the main model. With every part on, the engine answered 150 of the 170 questions. Without skills it answered 149, and without the citation check it answered 151. The check asked the model again on only 1 of the 170 questions, because only 1 of the 145 places the model cited was not among what it had been shown. Without skills the total moved by one: one knowledge answer gained and two reasoning answers net lost. The run without the check differs from the full run by one retry, and its one score change was variation between runs. Twelve of the 120 knowledge answers cited no place, so the check had nothing to test there.

Figure 5.19 and Table 5.8 answer the question of how much to show. The engine was run again on the 120 knowledge questions with the amount shown fixed at four sizes, beside the fitted 17,417 characters. At 2,000 characters most questions received nothing, because the best piece did not fit, and 15 were answered. Accuracy then rose with every increase: 56 at 4,000 characters, 76 at 8,000, 102 at the fitted size and 112 at 32,000. The gain per token was highest at 2,000 characters (58.1 points for each 1,000 tokens), but only because 94 of the 120 questions there received nothing. Among budgets that delivered excerpts it fell from 27.9 at 4,000 characters to 7.8 at 32,000, and the time for an answer rose from 2.1 to 15.6 seconds.

!fig figures/v2/chart-sweep.png | Figure 5.19: Knowledge answers right against tokens read, as the amount of the vault shown to Gemma 4 12B grows | 6.2

!include generated2/sweep.md | Table 5.8

Figure 5.20 shows the speed of a lookup before and after the search was rebuilt, on an index of 11,710 pieces from the Django repository. Before the rebuild a lookup that followed links took a median of 2.87 seconds. After it the median was 0.18 seconds, about sixteen times faster. Plain search was already fast and stayed at about 0.15 seconds. On the 101 real bug fixes of the earlier evaluation the rebuilt search reached the same changed files as before on every question (59 by search, 72 by following links), although other files shown differed on 3 searches and 51 walks. That check used a build made just before the freeze.

!fig figures/v2/chart-speed.png | Figure 5.20: Median time of one lookup on the Django index, before and after the search was rebuilt | 5.6

### 5.5.6 Error Analysis

Of the engine's 18 wrong knowledge answers on the main model, 8 had a needed file missing from what was shown and 10 had every file shown. Both retrieval and the model's reading therefore still failed, as Joren et al. (2025) also found for small models given sufficient context. Table 5.9 shows one answer of each kind, taken from the saved results of the main model with the engine.

!tab Table 5.9: Examples of answers from Gemma 4 12B with the engine
!widths 1.05,2.0,2.05,1.2
| Outcome | Question, in short | The model's answer | What happened |
| Right, with its source | How long is the Data Commissioner's term of office, and can it be renewed? | The Data Commissioner shall be appointed for a single term of six years and shall not be eligible for a re-appointment. (Law/act-part-02-office-of-the-data-commissioner.md:71) | The file was found and the place was cited. |
| Incomplete | Which statute guides the Data Commissioner before cancelling a certificate, and what is the maximum fine under the general penalty? | The Fair Administrative Actions Act, 2015 was named, and the model stated that it did not know the maximum fine from what it was shown. | One of the three needed files was not shown, and the model declined that half. |
| Refused, with the evidence shown | Within how many hours of a personal data breach must a data controller notify the Data Commissioner? | I don't know from what you were shown. | The needed file was among the excerpts, and the model did not use it. |
| Refused, with the evidence missing | Which model and context size were tried for Claude Code through Ollama? | I don't know from what you were shown. | Ollama release notes were shown and the project's decision log was not. The refusal was correct. |
| Right, vault left out | A GSM8K problem on the ounces of meat eaten by a basketball team | Answer: 30 | The engine left the vault out, and the model read 272 tokens. |

## 5.6 System Testing

### 5.6.1 Test Strategy and Acceptance Criteria

Testing was done at three levels. Unit tests checked each type of the library alone. Integration tests ran the whole loop from a question to a kept note with a scripted model, so that a result does not depend on what a real model happens to say. System test cases then verified each requirement of Chapter 4, by automated test, by running the frozen program, by using the desktop app, or by inspection where the requirement concerns how the system is built. The tests included normal cases, wrong input, and failures of the model service. The acceptance criterion was that every automated test passed on the frozen source and that every requirement of Chapter 4 had a test case whose observed result equalled its expected result. No person other than the developer has used the app, so no user acceptance test is claimed.

The engine has 212 automated tests, and all of them passed on the frozen source. The full record is saved in the repository as unit-tests-evaluation-2.log.

### 5.6.2 Test Cases, Defects and Retesting

Twenty-three test cases were run, one or more for every requirement, and all passed, three of them with a stated condition. Table 5.10 gives the ten that cover the core workflow and its failure conditions; the full record of all 23 is in the repository (https://github.com/Satasdin/CAMR/blob/burrow/docs/evaluation/test-cases.md), with a table tracing each requirement to its component and test (https://github.com/Satasdin/CAMR/blob/burrow/docs/evaluation/traceability.md).

!tab Table 5.10: Key test cases and results (all 23 are in the repository)
!widths 0.55,1.05,1.5,1.25,1.25,0.7
| Test ID | Requirement | Scenario and test data | Expected result | Actual result and evidence | Verdict |
| TC-01 | FR-01 | A vault indexed twice, then with one file changed and one removed | Nothing rebuilt the second time; old words gone the third time | As expected; test log | Pass |
| TC-04 | FR-04 | A question the vault knows nothing about | The vault is left out | Left out; the model received only the question; test log | Pass |
| TC-05 | FR-04 | The 50 reasoning problems of Section 5.5, on the frozen program | The vault is left out | Left out on 50 of 50; saved results | Pass |
| TC-08 | FR-07, IR-01 | A question on the command line; a question about a regulation asked by Gemma 4 12B in OpenCode through MCP | An answer naming file and line, with the decision line; in the app, each lookup and the files read | As in Figures 5.3 and 5.6 | Pass |
| TC-09 | FR-08 | An answer citing a file it was not shown, with a scripted model | One retry; the better grounded answer kept | As expected; test log | Pass |
| TC-11 | FR-10, IR-03 | vault_prepare called through MCP; a tool called before initialising | The decision and excerpts, no chat model called; the early call refused | As in Figure 5.10; test log | Pass |
| TC-12 | NFR-02 | The index deleted and rebuilt | No note lost; same pieces and links | As expected; test log | Pass |
| TC-17 | NFR-06 | swift test on the frozen source; the package file inspected | 212 tests pass; no third-party package | As expected; test log | Pass on one machine |
| TC-21 | IR-02 | Ollama unreachable during a search and during an answer | Search continues on words; the failure is reported | As expected; test log | Pass |
| TC-23 | IR-05 | The published install command run into an empty folder with the application option; the landing page and its download link fetched | Program and application installed, checksums pass, the program indexes a vault; page and link return successfully | As expected. The browser download on a second computer was not tried | Pass on one machine |

Five defects were recorded. Two affected the runs and were corrected and retested. The first cloud run was stopped after 35 questions because the harness cut answers at 600 tokens, and the limit was raised to 4,000. A budget sweep was stopped because it had begun while another run was using the machine. Both were restarted from the first question, and the partial runs are kept in the repository. Three are known gaps that remain in the frozen code and were left unfixed, so that the engine measured is the engine described. They are stated with the other limitations in Section 5.9.6.

## 5.7 Version Control and Implementation Evidence

Project repository: https://github.com/Satasdin/CAMR, with burrow as its default branch. Figure 5.21 shows the history of the engine's source, the tags and the folders. The engine is in Sources, its tests in Tests, the desktop app in app, the evaluation in trials, and this report with its scripts in docs/report. The README states the problem, the set-up, and how to run and test the system.

!fig figures/screens2/console-git.png | Figure 5.21: The history of the engine's source, the tags and the folders of the repository | 6.2

The workflow supported the evaluation directly. Each evaluation was run on a tagged, frozen version. The tag evaluation-1 marks retrieval before the engine's steps, and evaluation-2 marks the engine measured in this chapter. The hash of the frozen program is saved in trials/results/gap-1 and in each set-up's meta.json, and the harness refuses to add answers from a different program to the same folder. A reported number can therefore be traced to the exact code that produced it.

Every push to the repository also runs the automated tests on a hosted Apple silicon machine through GitHub Actions, and the log of each run is kept with its commit. The first run, on 12 November 2026, failed to compile: one line of the retrieval code used a form that the hosted Swift compiler did not accept, although the newer compiler on the development laptop did. The line was corrected, and the next run built the engine and passed every test. The release burrow-v1.1.0 was published from that tested commit.

## 5.8 Author Oversight and Use of AI-Assisted Tools

Claude Code, a coding assistant from Anthropic running Claude Opus 5.5, wrote most of the code, tests and experiment scripts in both increments, ran the experiments, made the figures, and drafted the report from the saved results, at the author's direction and from the author's design. Kimi K3 from Moonshot AI was used in the first increment as a model under test and as a judge of answers, and Claude through its API was the cloud model in the experiments. Every output was checked against the automated tests, the saved results, and the cited sources. The author chose the experiments, made the final decisions, and takes full responsibility for the submitted work. Appendix 3 gives the AI-use log, and the user guide is in the repository (https://github.com/Satasdin/CAMR/blob/burrow/docs/evaluation/user-guide.md).

## 5.9 Evaluation Results, Discussion and Limitations

This section takes each specific objective with its research question in turn. For each it states the output, the evidence, the criterion, the observed result, and what the result permits the study to conclude.

### 5.9.1 Objective i: The Capability Gap and Existing Techniques

The first research question asked what the capability gaps are and how far existing techniques apply on a device. The output is the review in Chapter 2, and the criterion was a stated gap supported by the literature. The review found that the gap is concentrated in long-tail knowledge (Kandpal et al., 2023; Mallen et al., 2023), that retrieval can stand in for scale but can also harm an answer (Shi et al., 2023; Yoran et al., 2024), and that no reviewed work measures gap closing by a memory engine alone on a consumer device, by task type. The objective was met, and the gap it identified is the one the remaining objectives addressed.

### 5.9.2 Objective ii: The Design of the Engine

The second research question asked how the engine can be designed in terms of its write policy, retrieval policy, and token budgeting mechanism. The output is the design in Chapter 4, and the criterion was a designed component for each of the three mechanisms. Learn is the write policy, Decide with ranking by words, meaning, and links is the retrieval policy, and Fit is the token budgeting mechanism (Figure 4.7). The objective was partly met. Each of the three mechanisms was designed and built, but two not as the objective worded them. The write policy proposes notes from a conversation for the person to approve, rather than distilling every interaction, and its effect on later answers was not measured. Recency and importance were added as tie-breakers after Evaluation 2 was frozen, so its scores do not include them; on its 120 questions with evidence, search found the evidence for 105 both before and after, so on this material they neither helped nor harmed, and their benefit on a vault where notes go out of date was not measured.

### 5.9.3 Objective iii: The Development of the Engine

The third research question asked how the engine can be developed on a consumer laptop with no dedicated graphics hardware, using an embedded database. The output is the engine of Section 5.4, in Swift with an embedded SQLite index, and the criterion was the acceptance criterion of Section 5.6.1. All 212 automated tests passed on the frozen source and all 23 test cases met their expected results, four of them within a stated limit (TC-14, TC-17, TC-22, and TC-23). A lookup that followed links took a median of 0.18 seconds on an index of 11,710 pieces. The objective was met on the one laptop tested.

### 5.9.4 Objective iv: The Fraction of the Gap Closed and Its Cost

The fourth research question asked what fraction of the gap the engine closes on each task type and at what cost. The output is the evaluation of Section 5.5, and the criteria were the predictions written before the runs: that the engine would close most of the gap on knowledge tasks, and little or none on reasoning tasks, and that it would read more tokens than plain retrieval on the main model. The first and third predictions held, and on reasoning the fraction is not reported because the gap was too small to measure.

On knowledge, measured against the cloud model given the same vault (109 of 120), the engine closed 93% of the gap. It was 7 questions behind (0 gained, 7 lost, p = 0.016), with Claude shown more text. Against the cloud model alone (40 of 120) the fraction is 300%, which shows that the cloud model alone is a weak ceiling for this material, much of which it could not have seen (Section 5.5.3). What the engine closed is therefore a gap in access to knowledge, which any retrieval narrows; plain retrieval alone reached 94 of 120. The result agrees with Mallen et al. (2023), who found that retrieval helps most on less popular facts. Narayan et al. (2025) measured a related quantity, the share of a cloud model's performance that a local-cloud protocol keeps (87%), by having the on-device model work with a cloud model. Burrow kept everything on the device.

Memory given to a reasoning task did harm: plain retrieval cut the model from 47 to 7 of 50 problems. The engine's first step removed that harm by deciding, on all 50 problems, that the vault was not needed. Shi et al. (2023) and Mirzadeh et al. (2025) showed that irrelevant sentences added to grade-school problems sharply reduce accuracy. Here the failure was mainly refusal: told to answer only from excerpts that did not hold the answer, the model said that it did not know. It varied by prompt and model, since Chroma's pipeline solved 42 on the main model and 1 on the small model. This is the clearest difference between an engine and a database. A database answers every query it is given, and an engine decides whether the query should be made.

The engine was shown more than either baseline: 17,417 characters against 12,000. Against plain retrieval it gained 10 knowledge questions and lost 2 (p = 0.039, uncorrected across 16 paired tests, so it does not survive a Bonferroni correction), and against Chroma it gained 34 and lost 7 (p < 0.001). All 10 gains came on questions sent to plain search, where the engine read the same ranking with a larger budget, and on the 28 questions where it followed links it neither gained nor lost. On the small model, with both limited to 12,000 characters, the engine found the evidence as often (103 against 102) and answered fewer (91 against 97). The gain on the main model therefore came mainly from the larger budget.

On cost, a knowledge answer took a median of about nine seconds on the laptop and read about 6,100 tokens, and a reasoning answer took 3.4 seconds and read 238. Almost all of the time was the model reading and writing. On the local runs the engine's own share was under a tenth of a second. When prepared for Claude, on a busy machine, the same step took a median of 3.6 seconds. The objective was partly met. The fraction and its cost were measured for knowledge, where the engine closed 93% of the gap to the cloud model with the same vault at a small cost of its own, and the engine protected reasoning. On reasoning, however, the gap was too small to give a fraction, and on knowledge the engine's gain over plain retrieval came mainly from its larger budget, so the study permits the conclusion that memory closed most of the gap on this material and this laptop, not that the engine's decisions did.

### 5.9.5 Objective v: The Token Budget

The fifth research question asked which token budget maximises the gap closed per token and how gap closure changes with the budget. The output is the budget sweep of Section 5.5.5. No criterion was set in advance, because the sweep was added after the plan. Among budgets that delivered excerpts, the gain per token was highest at 4,000 characters and fell as more was shown. Accuracy itself did not peak inside the range tested: at 32,000 characters the on-device model answered 112 of 120, at 15.6 seconds an answer. That is 3 more than the cloud model with Burrow, a difference that is not significant (4 gained, 1 lost, p = 0.375), and Claude was shown 24,000 characters. The fitted budget of about 17,000 characters, which the engine chose from the model's reading speed, sat between the two at 102 right in 9.2 seconds. The objective was partly met. The sweep showed how gap closure changes with the budget, but it did not determine a single budget that maximises it: gain per token was highest at the smallest budget that delivered anything, while accuracy kept rising, so the budget is a choice between speed and accuracy that the engine exposes, and five budgets run once each cannot fix it more precisely.

Table 5.11 summarises the five objectives.

!tab Table 5.11: How each specific objective was met
!widths 0.4,2.0,0.9,3.0
| No. | Objective, in short | Evidence | Verdict and observed result |
| i | Investigate the capability gap and existing memory techniques | Chapter 2 | Met. No measurement of gap closing on a device by task type was found |
| ii | Design the memory engine | Chapter 4 | Partly met. Write policy, retrieval policy (words, meaning, links, then recency and importance) and token budget designed and built; the write policy's effect and the recency and importance signals were not measured |
| iii | Develop the engine on a consumer laptop | Sections 5.4, 5.6 | Met on one laptop. Swift with an embedded SQLite index; 212 automated tests and 23 test cases passed |
| iv | Measure the fraction of the gap closed, by task type, with cost | Section 5.5.3 | Partly met. 93% of the gap to the cloud model with the same vault closed on knowledge (9 to 102 of 120); reasoning protected (47 to 48 of 50) but its gap too small for a fraction; a median of about 9 seconds and 6,100 tokens for a knowledge answer |
| v | Determine the token budget | Section 5.5.5 | Partly met. Gain per token highest at 4,000 characters among budgets that delivered excerpts; accuracy rose up to the largest budget tested, so no single best budget was found |

### 5.9.6 Limitations

The results have limits, and each is stated here with its likely effect. First, skills and the citation check did not change the scores: the engine answered 150 of 170 questions with both, 149 without skills, and 151 without the check, so they are working features whose benefit this evaluation did not show. Second, the scored runs compared budgets of different sizes, so the engine's gain over the baselines cannot be credited to its decisions alone, and Decide and Fit were not switched off separately. Third, on the small model the engine did not beat plain retrieval on knowledge, answering 91 against 97, so the gain does not carry to every model. Fourth, the knowledge questions were written by Claude Code agents, from the same family as the cloud reference model, and scored by answer keys, so a right string in a wrong sentence counts as right, and the questions may be easier or harder than a person's own. Fifth, each question was run once on one laptop, and other jobs shared the machine during some runs, so the times are indicative. Sixth, the Learn step was tested only by automated tests, and no experiment measured its effect on later answers. Seventh, no person other than the developer has used the app, so its usability is not claimed. Eighth, three known gaps remain in the frozen code: the check with retry runs only on the command burrow ask --mode engine, and the chat and MCP do not check; the MCP tool and the terminal chat use a fixed budget of 12,000 characters and not the fitted one; and the engine's own prompt does not stop an excerpt from closing its block. Ninth, two trials outside the objectives, a coding trial and a third evaluation of session memory, are reported with the further results in the repository and do not bear on the conclusions.

Chapter 6 draws the conclusions of the study from these results.
