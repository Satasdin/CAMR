# Chapter 5:  System Implementation, Testing and Evaluation

## 5.1 Introduction

This chapter presents how the design of Chapter 4 was implemented, tested, and evaluated, and it addresses the third, fourth, and fifth specific objectives. The study followed the artificial intelligence route of the data-to-model workflow. Section 5.2 states the implementation environment, Section 5.3 describes the dataset and its preparation, and Section 5.4 presents each part of the engine in the order of the architecture in Chapter 4. Section 5.5 evaluates the models, Section 5.6 reports the system tests, and Sections 5.7 and 5.8 give the version control evidence and the declaration of AI-assisted tools. Section 5.9 discusses the results against each specific objective and research question, and states their limitations. Every results table and chart was produced by a script from saved answers, and the scripts are in the repository beside the results.

## 5.2 Implementation Environment

Burrow is meant for a consumer computer that can run a local model service. It was developed and tested on one laptop of that kind, and it is published for download from a public landing page. The models ran in Ollama on the same machine, and the cloud model was called only by the evaluation harness.

### 5.2.1 Hardware and Deployment Environment

Table 5.1 states what the system needs and the machine on which it was tested. That is the only configuration tested, so other computers and operating systems are not claimed.

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

The release path of Section 4.4.5 is live. The landing page at https://satasdin.github.io/CAMR offers the desktop application and the one-command install from the release burrow-v1.0.0, for Apple silicon and macOS 14 or later. The application is not signed with Apple, so on first open after a browser download macOS requires the person to choose Open Anyway; installing it with the command avoids this step. The system can also be built from source. A person needs the Swift toolchain and Ollama, and pulls the two models with ollama pull gemma4:12b and ollama pull qwen3-embedding:0.6b. The command swift build -c release builds the command-line tool, and app/build.sh builds the desktop application. The command burrow index builds the index of a vault, and burrow fit measures the model once. A first question through burrow ask verifies that the installation works. The evaluation is repeated by following trials/gap/README.md in the repository. Everything runs locally except the two cloud set-ups, which need a paid key for the Claude service. No dataset in the study is restricted.

## 5.3 Dataset Description

### 5.3.1 Description of the Dataset

The evaluation used one vault of real documents and 170 questions. The material suits the objective because an on-device model cannot know it well: it is law specific to Kenya, software documentation dated 2026, and a private project. Table 5.3 describes it. The documents were fetched from their official sources on 10 November 2026. The private project is Burrow's own source code and decision log at an earlier tagged version, written days before the evaluation.

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

The vault is an ordinary folder that the person chooses, which implements FR-01 and DR-01. Figure 5.1 shows the graph of a vault in the desktop app. Each dot is a note or a file, each line is a link, and the colours are folders. This is the evaluation vault of Section 5.3. It holds 59 notes and 37 code files, joined by 290 links.

!fig figures/screens3/graph.png | Figure 5.1: The graph of a vault in the desktop app, coloured by folder | 6.2

Figure 5.2 shows a sample note being edited. The note is a plain Markdown file, and the panel on the right draws its neighbours and lists its properties.

!fig figures/screens3/note.png | Figure 5.2: A note in the desktop app, with its links and properties | 6.2

### 5.4.2 Decide

For every question the engine runs one fast search and reads its signal. It then decides whether the vault is needed and how to read it, which implements FR-04 and FR-05. Figure 5.3 shows a question about code on the command line. The engine followed the links between files, handed the model the skill for explaining code, and reported what it read.

!fig figures/screens2/console-engine.png | Figure 5.3: The engine answering a question about code and reporting its decision, the skill used, the files read and the citation check | 6.2

Figure 5.4 shows the opposite decision in the desktop app. The question is a sum, so the engine left the vault out and gave the model the skill for working a calculation. The line under the answer says so.

!fig figures/screens3/ask-sum.png | Figure 5.4: A sum in the desktop app, answered with the vault left out | 6.2

### 5.4.3 Fit

The engine measures a model once and keeps the result with the vault, which implements FR-06. Figure 5.5 shows a measurement of the main model and the list of skills the vault holds.

!fig figures/screens2/console-fit.png | Figure 5.5: Measuring a model once with burrow fit, and the skills in the vault | 6.2

For the scored runs Gemma 4 12B was measured at about 670 tokens a second and was shown 17,417 characters of the vault in a window of 16,384 tokens. The smaller model was shown 12,000 characters. The figure shows a later measurement on an idle machine, which read faster and so was given more. The fit depends on what else the machine is doing when it is taken.

### 5.4.4 Answer and Check

Figure 5.6 shows a question about a document answered in the desktop app, which implements FR-07 and IR-01. Under the answer the app states the decision, the skill and the files that were read, and each file opens at the lines that were read.

!fig figures/screens3/ask-law.png | Figure 5.6: A question answered from the vault in the desktop app, with the engine's decision and the files read | 6.2

Figure 5.7 shows the same moment from the graph. The files the model was shown light up while the answer is written, so the person can see what the model read.

!fig figures/screens3/graph-ask.png | Figure 5.7: The files read for an answer lighting up in the graph | 6.2

On the command line every file and line in the answer is compared with what the model was shown, and the model is asked once more if a citation was not among them, which implements FR-08. Figure 5.8 shows what happens when the excerpts do not hold the answer. The question is about Ugandan law, which the vault does not contain. The model says that it does not know, and the app still lists what was read.

!fig figures/screens3/ask-miss.png | Figure 5.8: A question the excerpts could not answer, and the model saying so | 6.2

### 5.4.5 Skills and Learn

A skill is a Markdown file in the vault's Skills folder. Figure 5.9 shows one. The line beginning with the word when is what a question is matched against, and the numbered steps are what the model is given. A person can edit a skill or add a new one as an ordinary note.

!fig figures/screens2/console-skill.png | Figure 5.9: A skill as it is stored in the vault | 6.2

After a conversation the engine can propose up to three notes of what the person decided, which implements FR-09 and DR-03. In the terminal chat's /keep command, a note is offered only if its quote is found in the person's own words, and it is written only when the person accepts it. The app proposes notes without the quote check and writes each one only on Keep. The command burrow learn applies the quote check but does not ask, and over MCP consent rests with the client.

### 5.4.6 Serving Other Models and Tools

The engine is not tied to the model it hosts, which implements FR-10 and IR-03. Figure 5.10 shows an outside client asking Burrow to prepare a task through the Model Context Protocol. Burrow returns its decision and the excerpts without calling a chat model.

!fig figures/screens2/console-mcp.png | Figure 5.10: An outside client calling the tool vault_prepare through the Model Context Protocol | 6.2

Figure 5.11 shows Burrow used as the retriever inside a LangChain pipeline, in the place where a vector database would normally sit.

!fig figures/screens2/console-langchain.png | Figure 5.11: Burrow as the retriever in a LangChain pipeline | 6.2

### 5.4.7 Deviations from the Approved Design

Four parts of the build differ from the proposal. The memory became a vault of files that a person writes instead of a stream of notes from each interaction, because the Sprint II review asked for something a person can see and use. Ranking by recency and importance was therefore not built, and ranking uses what the files provide, namely their words, their meaning, and the links between them; the effect of recency and importance was not measured. The Check step was added during the study, because a small model's citations can be compared directly with what it was shown. The engine was also written in Swift in place of Python, so that it runs as one compiled program on the target platform.

## 5.5 Model Selection and Evaluation

### 5.5.1 Baselines and Set-ups

No model was trained or fine-tuned. The on-device models were selected because they are recent open-weight models sized for the laptop, and they were used as published. Local answers were generated at temperature 0 with a fixed seed, but repeated runs still differed: of 169 identical prompts run twice, 41 answers changed in wording and one changed in score. The cloud model does not accept a temperature setting.

The same 170 questions were put to six set-ups, which Table 5.4 lists. Set-ups 1 to 4 were run with Gemma 4 12B and again with Qwen3.5 4B. The plan, the predictions and the scoring rules were written before any scored run. The budget sweep, the website trial and the reporting threshold in Table 5.6 were added after the plan, and the cloud model could not be run at temperature 0 as planned.

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

The fraction of the capability gap closed is Equation 3.1, where the floor is the on-device model alone and the ceiling is the cloud model alone. Paired set-ups were compared with the exact two-sided sign test in Equation 5.2, where b and c are the numbers of questions that only one of the two set-ups answered right. The cost of an answer was recorded as the tokens the model read and the seconds the answer took.

!eq sign | Equation 5.2: Exact two-sided sign test on paired answers

### 5.5.3 Results on the Main Model

Figure 5.12 and Table 5.5 give the answers right for the main model. Alone, Gemma 4 12B answered 9 of the 120 knowledge questions. With the engine it answered 102. The cloud model alone answered 40, and 109 when it was given the same vault, prepared by the engine with a limit of 24,000 characters.

!fig figures/v2/chart-accuracy-main.png | Figure 5.12: Answers right by set-up and task type, Gemma 4 12B and the cloud model | 6.2

!include generated2/accuracy-gemma4-12b.md | Table 5.5

The reasoning column shows the opposite effect. Alone, the model solved 47 of 50 problems. With plain retrieval it solved 7: on 43 of the 50 it replied that it did not know from what it had been shown, as the retrieval prompt instructs when the excerpts lack the answer. With the Chroma baseline, whose prompt has a similar rule, it solved 42. The engine left the vault out of all 50 and the model solved 48.

Table 5.6 gives the fraction of the gap closed. On knowledge questions the on-device model with the engine passed the cloud model alone, so the fraction is above 100%. On reasoning questions the ceiling was only 2 questions above the floor on Gemma 4 12B and 3 on Qwen3.5 4B, so the fraction, 50% and 100%, swings on a single answer. By a rule added after the plan, Table 5.6 does not report a fraction when the gap is under ten points.

!include generated2/gap.md | Table 5.6 | 1.15,1.25,0.95,0.95,0.8,0.7,0.7

Table 5.7 gives the cost. The engine showed the main model more of the vault than plain retrieval did, about 6,100 tokens against 3,800, and an answer took 9.2 seconds against 8.3. The engine's own work before the model started took 0.06 seconds. The engine brought back every file holding the answer on 111 of 120 questions, against 102 for plain retrieval and 95 for Chroma.

!include generated2/cost.md | Table 5.7 | 1.15,1.5,0.8,0.8,0.9,1.15

### 5.5.4 Results on the Small Model

The smaller model gave a mixed result, shown in Figure 5.13. Alone, Qwen3.5 4B answered 6 of the 120 knowledge questions. With plain retrieval it answered 97, with the Chroma baseline 75, and with the engine 91. On knowledge the engine therefore did not improve on plain retrieval for this model (1 question gained and 7 lost, p = 0.070). On reasoning the pattern of the main model repeated more sharply: 46 of 50 alone, 9 with plain retrieval, 1 with the Chroma pipeline, and 49 with the engine.

!fig figures/v2/chart-accuracy-small.png | Figure 5.13: Answers right by set-up and task type, Qwen3.5 4B and the cloud model | 6.2

### 5.5.5 Ablation, Budget and Speed

Two parts of the engine were switched off in turn on the main model. With every part on, the engine answered 150 of the 170 questions. Without skills it answered 149, and without the citation check it answered 151. The check asked the model again on only 1 of the 170 questions, because only 1 of the 145 places the model cited was not among what it had been shown. Without skills the total moved by one: one knowledge answer gained and two reasoning answers net lost. The run without the check differs from the full run by one retry, and its one score change was variation between runs. Twelve of the 120 knowledge answers cited no place, so the check had nothing to test there.

Figure 5.14 and Table 5.8 answer the question of how much to show. The engine was run again on the 120 knowledge questions with the amount shown fixed at four sizes, beside the fitted 17,417 characters. At 2,000 characters most questions received nothing, because the best piece did not fit, and 15 were answered. Accuracy then rose with every increase: 56 at 4,000 characters, 76 at 8,000, 102 at the fitted size and 112 at 32,000. The gain per token was highest at 2,000 characters (58.1 points for each 1,000 tokens), but only because 94 of the 120 questions there received nothing. Among budgets that delivered excerpts it fell from 27.9 at 4,000 characters to 7.8 at 32,000, and the time for an answer rose from 2.1 to 15.6 seconds.

!fig figures/v2/chart-sweep.png | Figure 5.14: Knowledge answers right against tokens read, as the amount of the vault shown to Gemma 4 12B grows | 6.2

!include generated2/sweep.md | Table 5.8

Figure 5.15 shows the speed of a lookup before and after the search was rebuilt, on an index of 11,710 pieces from the Django repository. Before the rebuild a lookup that followed links took a median of 2.87 seconds. After it the median was 0.18 seconds, about sixteen times faster. Plain search was already fast and stayed at about 0.15 seconds. On the 101 real bug fixes of the earlier evaluation the rebuilt search reached the same changed files as before on every question (59 by search, 72 by following links), although other files shown differed on 3 searches and 51 walks. That check used a build made just before the freeze.

!fig figures/v2/chart-speed.png | Figure 5.15: Median time of one lookup on the Django index, before and after the search was rebuilt | 5.6

### 5.5.6 Error Analysis

Of the engine's 18 wrong knowledge answers on the main model, 8 had a needed file missing from what was shown and 10 had every file shown. Both retrieval and the model's reading therefore still fail, as Joren et al. (2025) also found for small models given sufficient context. Table 5.9 shows one answer of each kind, taken from the saved results of the main model with the engine.

!tab Table 5.9: Examples of answers from Gemma 4 12B with the engine
!widths 1.05,2.0,2.05,1.2
| Outcome | Question, in short | The model's answer | What happened |
| Right, with its source | How long is the Data Commissioner's term of office, and can it be renewed? | The Data Commissioner shall be appointed for a single term of six years and shall not be eligible for a re-appointment. (Law/act-part-02-office-of-the-data-commissioner.md:71) | The file was found and the place was cited. |
| Incomplete | Which statute guides the Data Commissioner before cancelling a certificate, and what is the maximum fine under the general penalty? | The Fair Administrative Actions Act, 2015 was named, and the model stated that it did not know the maximum fine from what it was shown. | One of the three needed files was not shown, and the model declined that half. |
| Refused, with the evidence shown | Within how many hours of a personal data breach must a data controller notify the Data Commissioner? | I don't know from what you were shown. | The needed file was among the excerpts, and the model did not use it. |
| Refused, with the evidence missing | Which model and context size were tried for Claude Code through Ollama? | I don't know from what you were shown. | Ollama release notes were shown and the project's decision log was not. The refusal was correct. |
| Right, vault left out | A GSM8K problem on the ounces of meat eaten by a basketball team | Answer: 30 | The engine left the vault out, and the model read 272 tokens. |

### 5.5.7 A Coding Trial Against the Cloud Model

A small trial asked whether the on-device model can build something beside the cloud model. Three briefs for a single-file website were given to Gemma 4 12B and to Claude: a matatu fare splitter, a clinic queue board that survives a reload, and a landing page with a phone menu and a pricing toggle. Each page was scored in a real browser with the same fixed checks, 42 in all. Figure 5.16 shows the pages.

!fig figures/v2/web-compare.png | Figure 5.16: The same three briefs built by Gemma 4 12B alone, by Gemma with a skill and a note of known failures, and by Claude alone | 6.2

Claude passed all 42 checks in every set-up. Gemma alone passed 41. With the brief the engine prepared, which carried a web-building skill, Gemma passed 39, because one page had a script error. With the skill and a note of known failures handed over directly, it passed 41, and that run had no such error. The engine had left the note out, because it judged each brief to be a task to work out. The trial is three briefs run once, so it is a demonstration and not a measurement.

### 5.5.8 Evaluation 3: Memory Any Model Can Pick Up

A third evaluation tested the Ledger, Burrow's record of what earlier sessions understood, decided, were corrected on, and where they stopped. Its plan was written before any of these parts existed and before any scored run, and the engine was frozen for it as a separate binary. A smoke run found two faults in the engine and two in the harness before scoring, and all four were fixed and recorded in the plan. Every answer was scored by the rule of Equation 5.1, and paired set-ups by the sign test of Equation 5.2. Figure 5.17 shows the four tests.

!fig figures/v3/chart-eval3.png | Figure 5.17: The four tests of Evaluation 3: carrying on a conversation, notes from a bigger model, saying the vault does not hold an answer, and four tools against twelve | 6.2

The first test asked whether a model that lost its memory can carry on a conversation. One local model held a conversation of three questions, and the other local model was then asked what had been answered, given nothing, the transcript pasted in, the session tools of Section 5.4.6, or the Ledger's handoff. Table 5.10 gives the results. Nothing gave no right answers. The Ledger gave 11 of 30, against 6 of 30 for the session tools, and it read a median of 1,843 tokens against 3,525. The pasted transcript gave 18 of 30 and read 6,058. The transcript beat the Ledger on 8 questions and lost on 1 (p = 0.039), so the prediction that the Ledger would match it was not met, while the Ledger's gain over the session tools was not significant (7 against 2, p = 0.180).

!include generated3/e1-resume.md | Table 5.10

The second test asked whether notes left by the cloud model help the small model on other questions. The 80 knowledge questions were split by a fixed seed. Claude answered half A with Burrow and kept 76 facts it had confirmed in the files, and none cited a file it had not been shown. Qwen3 4B then answered half B. Table 5.11 gives the results. Burrow lifted it from 1 to 28 of 40, well above Claude alone at 19, but the notes added nothing: 29 of 40 with them, 2 questions gained and 1 lost (p = 1.000), although they reached the model on 37 of the 40 questions. The first scored run of this arm had cut every tool result at 12,000 characters, so the notes never reached the model; it was run again with whole results, and the plan records both runs.

!include generated3/e2-notes.md | Table 5.11

The third test asked whether the small model says when the vault does not hold an answer. A separate agent wrote 30 questions close to the vault's subjects whose answers are not in it, each checked against the vault's text, and these were mixed with 30 answerable questions. Table 5.12 gives the results. Without the trust line Qwen3 4B already said the vault did not hold the answer on 26 of the 30, and with it the count was the same; on the answerable questions it got 26 and 25 right and wrongly declined 2 in each set-up (p = 1.000). The prediction of a clear rise was not met, because the model was already honest without it.

!include generated3/e3-trust.md | Table 5.12

The fourth test compared the four tools a model is shown by default with the twelve of Section 5.4.6, on 16 knowledge questions. Table 5.13 gives the results. Gemma 4 12B answered all 16 either way. Qwen3 4B answered 11 with four tools and 14 with twelve; the three it lost were each answered after a single search in both set-ups, and the difference was not significant (p = 0.250). Every model looked up the vault on every question in both set-ups, so the small model's earlier trouble choosing a tool, which the catalogue in each tool's description had already solved, did not appear here.

!include generated3/e4-door.md | Table 5.13

## 5.6 System Testing

### 5.6.1 Test Strategy and Acceptance Criteria

Testing was done at three levels. Unit tests checked each type of the library alone. Integration tests ran the whole loop from a question to a kept note with a scripted model, so that a result does not depend on what a real model happens to say. System test cases then verified each requirement of Chapter 4, by automated test, by running the frozen program, by using the desktop app, or by inspection where the requirement concerns how the system is built. The tests include normal cases, wrong input, and failures of the model service. The acceptance criterion was that every automated test passes on the frozen source and that every requirement of Chapter 4 has a test case whose observed result equals its expected result. No person other than the developer has used the app, so no user acceptance test is claimed.

The engine has 212 automated tests, and all of them passed on the frozen source. The full record is saved in the repository as unit-tests-evaluation-2.log.

### 5.6.2 Test Cases, Defects and Retesting

Table 5.14 gives the test cases, with the requirement each one verifies.

!tab Table 5.14: Test cases and results
!widths 0.55,1.05,1.5,1.25,1.25,0.7
| Test ID | Requirement | Scenario and test data | Expected result | Actual result and evidence | Verdict |
| TC-01 | FR-01 | A vault indexed twice, then with one file changed and one removed | Nothing rebuilt the second time; old words gone the third time | As expected; test log | Pass |
| TC-02 | FR-02 | A question whose words are absent from the right file | The file is found by meaning | As expected; test log | Pass |
| TC-03 | FR-03 | A question naming only the first of three linked files | The third file is reached by following links | As expected; test log | Pass |
| TC-04 | FR-04 | A question the vault knows nothing about | The vault is left out | Left out; the model received only the question; test log | Pass |
| TC-05 | FR-04 | The 50 reasoning problems of Section 5.5, on the frozen program | The vault is left out | Left out on 50 of 50; saved results | Pass |
| TC-06 | FR-05 | A sum, with a calculation skill and a documents skill in the vault | The calculation skill and no excerpts | As expected; test log | Pass |
| TC-07 | FR-06 | A fast small model, a fast large model and a slow large model | 8,000, 24,000 and 6,400 characters | As expected; test log | Pass |
| TC-08 | FR-07, IR-01 | A question about a regulation, in the desktop app | An answer with the decision line and the files read | As in Figure 5.6 | Pass |
| TC-09 | FR-08 | An answer citing a file it was not shown, with a scripted model | One retry; the better grounded answer kept | As expected; test log | Pass |
| TC-10 | FR-09, DR-03 | Three proposed notes, one quoting words the person never typed; a note kept with and without agreement | Only the two backed by the person's words offered; nothing written without agreement | As expected; test log | Pass |
| TC-11 | FR-10, IR-03 | vault_prepare called through MCP; a tool called before initialising | The decision and excerpts, no chat model called; the early call refused | As in Figure 5.10; test log | Pass |
| TC-12 | NFR-02 | The index deleted and rebuilt | No note lost; same pieces and links | As expected; test log | Pass |
| TC-13 | NFR-01 | Inspection of the model client's source | Local model calls go to 127.0.0.1 | Default address 127.0.0.1:11434 in the source | Pass |
| TC-14 | NFR-03 | Excerpts returned by the search tool | Marked as material to read, with the notice | As expected on the tools path; test log | Pass on the tools path |
| TC-15 | NFR-04 | The 2,520 saved answer records checked by script | Tokens read and written and seconds on every record | Present on all; retrieval time absent only on the 170 cloud-alone records, which retrieve nothing | Pass |
| TC-16 | NFR-05 | Inspection of the storage code | One database file, a vector copy and two settings files; no server process | As expected | Pass |
| TC-17 | NFR-06 | swift test on the frozen source; the package file inspected | 212 tests pass; no third-party package | As expected; test log | Pass on one machine |
| TC-18 | DR-01 | A change attempted on a linked folder | The folder can be read and is not changed | As expected; test log | Pass |
| TC-19 | DR-02 | Inspection of the index tables against Figure 4.8 | File, lines, text and at most one vector per piece | As expected | Pass |
| TC-20 | DR-04 | The key-checking scripts; the location of the questions | Keys found in the source text and absent from their questions; questions outside the vault | As expected; key-checking script | Pass |
| TC-21 | IR-02 | Ollama unreachable during a search and during an answer | Search continues on words; the failure is reported | As expected; test log | Pass |
| TC-22 | IR-04 | A vault with links in double square brackets and Obsidian's own settings folder | The links join the notes; the settings are left out | As expected; test log. Not opened in Obsidian itself | Pass on format |
| TC-23 | IR-05 | The published install command run into an empty folder with the application option; the landing page and its download link fetched | Program and application installed, checksums pass, the program indexes a vault; page and link return successfully | As expected. The browser download on a second computer was not tried | Pass on one machine |

Five defects were recorded. Two affected the runs and were corrected and retested. The first cloud run was stopped after 35 questions because the harness cut answers at 600 tokens, and the limit was raised to 4,000. A budget sweep was stopped because it had begun while another run was using the machine. Both were restarted from the first question, and the partial runs are kept in the repository. Three are known gaps that remain in the frozen code and were left unfixed, so that the engine measured is the engine described. They are stated with the other limitations in Section 5.9.6.

## 5.7 Version Control and Implementation Evidence

Project repository: https://github.com/Satasdin/CAMR, with burrow as its default branch. Figure 5.18 shows the history of the engine's source, the tags and the folders. The engine is in Sources, its tests in Tests, the desktop app in app, the evaluation in trials, and this report with its scripts in docs/report. The README states the problem, the set-up, and how to run and test the system.

!fig figures/screens2/console-git.png | Figure 5.18: The history of the engine's source, the tags and the folders of the repository | 6.2

The workflow supported the evaluation directly. Each evaluation was run on a tagged, frozen version. The tag evaluation-1 marks retrieval before the engine's steps, and evaluation-2 marks the engine measured in this chapter. The hash of the frozen program is saved in trials/results/gap-1 and in each set-up's meta.json, and the harness refuses to add answers from a different program to the same folder. A reported number can therefore be traced to the exact code that produced it.

## 5.8 Author Oversight and Use of AI-Assisted Tools

Claude Code, a coding assistant from Anthropic, assisted with the system design, implementation, testing, and evaluation reported in Chapters 4 and 5, and with the drafting of those two chapters. Its output was checked against the automated tests, the saved results, and the cited sources. The author made the final decisions and takes full responsibility for the submitted work.

## 5.9 Evaluation Results, Discussion and Limitations

This section takes each specific objective with its research question in turn. For each it states the output, the evidence, the criterion, the observed result, and what the result permits the study to conclude.

### 5.9.1 Objective i: The Capability Gap and Existing Techniques

The first research question asked what the capability gaps are and how far existing techniques apply on a device. The output is the review in Chapter 2, and the criterion was a stated gap supported by the literature. The review found that the gap is concentrated in long-tail knowledge (Kandpal et al., 2023; Mallen et al., 2023), that retrieval can stand in for scale but can also harm an answer (Shi et al., 2023; Yoran et al., 2024), and that no reviewed work measures gap closing by a memory engine alone on a consumer device, by task type. The objective was met, and the gap it identified is the one the remaining objectives addressed.

### 5.9.2 Objective ii: The Design of the Engine

The second research question asked how the engine can be designed in terms of its write policy, retrieval policy, and token budgeting mechanism. The output is the design in Chapter 4, and the criterion was a designed component for each of the three mechanisms. Learn is the write policy, Decide with ranking by words, meaning, and links is the retrieval policy, and Fit is the token budgeting mechanism (Figure 4.7). The objective was met with one departure: the ranking by recency and importance that the objective names was not built, as Section 5.4.7 records, so the study cannot say what those two scores would have added.

### 5.9.3 Objective iii: The Development of the Engine

The third research question asked how the engine can be developed on a consumer laptop with no dedicated graphics hardware, using an embedded database. The output is the engine of Section 5.4, in Swift with an embedded SQLite index, and the criterion was the acceptance criterion of Section 5.6.1. All 212 automated tests passed on the frozen source and all 23 test cases met their expected results, four of them within a stated limit (TC-14, TC-17, TC-22, and TC-23). A lookup that followed links took a median of 0.18 seconds on an index of 11,710 pieces. The objective was met on the one laptop tested.

### 5.9.4 Objective iv: The Fraction of the Gap Closed and Its Cost

The fourth research question asked what fraction of the gap the engine closes on each task type and at what cost. The output is the evaluation of Section 5.5, and the criteria were the predictions written before the runs: that the engine would close most of the gap on knowledge tasks, and little or none on reasoning tasks, and that it would read more tokens than plain retrieval on the main model. The first and third predictions held, and on reasoning the fraction is not reported because the gap is too small to measure.

On knowledge the on-device model with the engine overtook the cloud model alone, 102 against 40 of 120, which is 300% by Equation 3.1. A figure above 100% means that the cloud model alone is a weak ceiling for this material, much of which it could not have seen. It scored 7 of 40 on the private project, 14 of 40 on the 2026 documents and 19 of 40 on the public Kenyan law. Against the cloud model with the vault (109), the engine closed 93% of the distance. It was 7 questions behind (p = 0.016), with Claude shown more text. The result agrees with Mallen et al. (2023), who found that retrieval helps most on less popular facts. Narayan et al. (2025) measured a related quantity, the share of a cloud model's performance that a local-cloud protocol keeps (87%), by having the on-device model work with a cloud model. Burrow kept everything on the device.

Memory given to a reasoning task did harm: plain retrieval cut the model from 47 to 7 of 50 problems. The engine's first step removed that harm by deciding, on all 50 problems, that the vault was not needed. Shi et al. (2023) and Mirzadeh et al. (2025) showed that irrelevant sentences added to grade-school problems sharply reduce accuracy. Here the failure was mainly refusal: told to answer only from excerpts that did not hold the answer, the model said that it did not know. It varied by prompt and model, since Chroma's pipeline solved 42 on the main model and 1 on the small model. This is the clearest difference between an engine and a database. A database answers every query it is given, and an engine decides whether the query should be made.

The engine was shown more than either baseline: 17,417 characters against 12,000. Against plain retrieval it gained 10 knowledge questions and lost 2 (p = 0.039, uncorrected across 16 paired tests), and against Chroma it gained 34 and lost 7 (p < 0.001). All 10 gains came on questions sent to plain search, where the engine reads the same ranking with a larger budget, and on the 28 questions where it followed links it neither gained nor lost. On the small model, with both limited to 12,000 characters, the engine found the evidence as often (103 against 102) and answered fewer (91 against 97). The gain on the main model therefore comes mainly from the larger budget.

On cost, a knowledge answer took a median of about nine seconds on the laptop and read about 6,100 tokens, and a reasoning answer took 3.4 seconds and read 238. Almost all of the time was the model reading and writing. On the local runs the engine's own share was under a tenth of a second. When prepared for Claude, on a busy machine, the same step took a median of 3.6 seconds. The objective was met: the study permits the conclusion that, on this material and this laptop, the engine closed the gap on knowledge and protected reasoning, at a small cost of its own.

### 5.9.5 Objective v: The Token Budget

The fifth research question asked which token budget maximises the gap closed per token and how gap closure changes with the budget. The output is the budget sweep of Section 5.5.5. No criterion was set in advance, because the sweep was added after the plan. Among budgets that delivered excerpts, the gain per token was highest at 4,000 characters and fell as more was shown. Accuracy itself did not peak inside the range tested: at 32,000 characters the on-device model answered 112 of 120, at 15.6 seconds an answer. That is 3 more than the cloud model with Burrow, a difference that is not significant (4 gained, 1 lost, p = 0.375), and Claude was shown 24,000 characters. The fitted budget of about 17,000 characters, which the engine chose from the model's reading speed, sits between the two at 102 right in 9.2 seconds. The objective was met, and the result is that the budget is a choice between speed and accuracy that the engine exposes, not a single best value.

Table 5.15 summarises the five objectives.

!tab Table 5.15: How each specific objective was met
!widths 0.4,2.0,0.9,3.0
| No. | Objective, in short | Evidence | Observed result |
| i | Investigate the capability gap and existing memory techniques | Chapter 2 | No measurement of gap closing on a device by task type was found |
| ii | Design the memory engine | Chapter 4 | Write policy, retrieval policy and token budget designed; ranking by recency and importance not built |
| iii | Develop the engine on a consumer laptop | Sections 5.4, 5.6 | Swift with an embedded SQLite index; 212 automated tests and 23 test cases passed |
| iv | Measure the fraction of the gap closed, by task type, with cost | Section 5.5.3 | 9 to 102 of 120 on knowledge, 47 to 48 of 50 on reasoning, with a median of about 9 seconds and 6,100 tokens for a knowledge answer |
| v | Determine the token budget | Section 5.5.5 | Gain per token highest at 4,000 characters among budgets that delivered excerpts; accuracy rose up to the largest budget tested |

### 5.9.6 Limitations

The results have limits, and each is stated here with its likely effect. First, skills and the citation check did not change the scores: the engine answered 150 of 170 questions with both, 149 without skills, and 151 without the check, so they are working features whose benefit this evaluation did not show. Second, the scored runs compared budgets of different sizes, so the engine's gain over the baselines cannot be credited to its decisions alone, and Decide and Fit were not switched off separately. Third, on the small model the engine did not beat plain retrieval on knowledge, answering 91 against 97, so the gain does not carry to every model. Fourth, the knowledge questions were written by Claude Code agents, from the same family as the cloud reference model, and scored by answer keys, so a right string in a wrong sentence counts as right, and the questions may be easier or harder than a person's own. Fifth, each question was run once on one laptop, and other jobs shared the machine during some runs, so the times are indicative. Sixth, the Learn step was tested only by automated tests, and no experiment measured its effect on later answers. Seventh, no person other than the developer has used the app, so its usability is not claimed. Eighth, three known gaps remain in the frozen code: the check with retry runs only on the command burrow ask --mode engine, while the app only warns and the chat and MCP do not check; the MCP tool and the terminal chat use a fixed budget of 12,000 characters and not the fitted one; and the engine's own prompt does not stop an excerpt from closing its block. Finally, Evaluation 3 ran each question once on two local models, with 15 to 40 questions per comparison, so a difference of a few answers between set-ups is within chance; of its four predictions, none was met in full, and the Ledger and the notes are reported as working parts whose benefit over a pasted transcript, or over Burrow without notes, this evaluation did not show.
