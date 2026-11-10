# Chapter 5:  System Implementation and Testing

## 5.1 Introduction

This chapter presents the engine as it was built and what the experiments measured. It states the environment, describes the dataset, shows each part of the engine at work, reports the experiments that answer the research questions, gives the system tests, and discusses the results against the objectives. Every number was produced by a script from saved answers, and the scripts are in the repository beside the results.

## 5.2 Implementation Environment

Burrow was built and tested on one laptop. The models ran in Ollama on the same machine. The cloud model was called only by the evaluation harness.

### 5.2.1 Hardware Specifications

Table 5.1 states the machine used. It is the only configuration tested.

!tab Table 5.1: Hardware specifications
!widths 1.5,4.8
| Component | Description and justification |
| Laptop | Apple MacBook Pro with an M5 Pro chip and 24 GB of shared memory. It runs the engine, the index and the local models together, which is the on-device setting the study is about. |
| Storage | Internal SSD. The index is one database file beside the vault, and the vectors are one file mapped into memory. |
| Graphics | The chip's own graphics processor, used by Ollama. No separate graphics card. |
| Network | Needed only to download models and to call the cloud model during evaluation. The engine works offline. |

### 5.2.2 Software Specifications

Table 5.2 lists the software and the models with their versions.

!tab Table 5.2: Software specifications
!widths 1.7,1.7,2.9
| Software | Version | Role |
| macOS | 27.2 | Operating system |
| Swift | 6.4.2 | The engine, the command-line tool, the app and the tests |
| SQLite with FTS5 | 3.54.0 | The embedded index: word search, vectors and links |
| Ollama | 0.40.14 | Runs the frozen local models on the device |
| Gemma 4 12B | `gemma4:12b`, 7.7 GB | The main on-device model |
| Qwen3.5 4B | `qwen3.5:4b`, 4.0 GB | The small on-device model |
| Qwen3 Embedding 0.6B | `qwen3-embedding:0.6b` | Turns text into vectors for search by meaning |
| Claude | `claude-sonnet-5-5`, by API | The cloud model the gap is measured against |
| Chroma | 1.5.9 | The vector database baseline |
| LangChain | langchain-core 0.3.86 | Shows Burrow working inside a framework |
| Python | 3.9.6 | The evaluation harness and the charts |

Local answers were generated at temperature 0 with a fixed seed, so a repeated run gives the same answer. The cloud model does not accept a temperature setting.

## 5.3 Description of the Dataset

The evaluation used one vault of real documents and 170 questions. Table 5.3 describes them. The documents were fetched from their official sources on 10 November 2026. The private project is Burrow's own source code and decision log at an earlier tagged version, which no model can have seen in training.

!tab Table 5.3: The evaluation vault and its questions
!widths 1.2,2.9,0.6,0.8,0.8
| Subject | Material | Files | One-fact questions | Several-fact questions |
| Kenyan law | Data Protection Act (Cap. 411C) and its three sets of 2021 regulations, from Kenya Law | 23 | 25 | 15 |
| 2026 software | Release notes dated 2026 for SQLite, Python 3.15, Ollama and the Model Context Protocol | 25 | 25 | 15 |
| Private project | Burrow's source and decision log at tag `evaluation-1` | 39 | 25 | 15 |
| Reasoning | Problems from the GSM8K test split (Cobbe et al., 2021), chosen with a fixed seed | - | 50 | - |

The 120 knowledge questions were written from the documents by a language model, with an answer key for each. A script checked every key against the quoted evidence and rejected any key that appeared in its own question. A several-fact question needs two passages from two different files. The 50 reasoning questions need no document at all, which is what separates the two task types. Appendix 3 shows one question of each kind.

The engine's thresholds were set on a separate set of development questions written by the developer. The scored questions were not read during development, and the engine was frozen before the first scored run.

## 5.4 System Implementation

The engine is one Swift library with four surfaces over it: a command-line tool, a Mac app, a terminal chat and a Model Context Protocol server. This section shows each of the engine's steps working.

### 5.4.1 Decide

For every question the engine runs one fast search and reads its signal. It then decides whether the vault is needed and how to read it. Figure 5.1 shows a question about code. The engine followed the links between files, handed the model the method for explaining code, and reported what it read.

!fig figures/screens2/console-engine.png | Figure 5.1: The engine answering a question about code and reporting its decision, the skill used, the files read and the citation check. | 6.2

Figure 5.2 shows the opposite decision in the Mac app. The question is a sum, so the engine left the vault out and gave the model the method for working a calculation.

!fig figures/screens2/app-sum.png | Figure 5.2: A sum in the Mac app. The line under the answer states that the vault was left out and which method was used. | 6.2

### 5.4.2 Fit

The engine measures a model once and keeps the result with the vault. Figure 5.3 shows the measurement of the main model and the list of skills the vault holds. For the scored runs Gemma 4 12B was measured at about 640 tokens a second and was shown 17,417 characters of the vault in a window of 16,384 tokens. The smaller model was shown 12,000 characters. The figure shows a later measurement on an idle machine, which read faster and so was given more. The fit depends on what else the machine is doing when it is taken.

!fig figures/screens2/console-fit.png | Figure 5.3: Measuring a model once with `burrow fit`, and the skills in the vault. | 6.2

### 5.4.3 Answer and Check

Figure 5.4 shows a question about a document in the Mac app. Under the answer the app states the decision, the method and the files that were read, and each file opens at the cited line. On the command line every file and line in the answer is compared with what the model was shown, and the model is asked once more if a citation was not among them.

!fig figures/screens2/app-ask.png | Figure 5.4: A question answered from the vault in the Mac app, with the engine's decision and the files read. | 6.2

### 5.4.4 Skills and Learn

A skill is a Markdown file in the vault's `Skills` folder. Figure 5.5 shows one. The line beginning `when:` is what a question is matched against, and the numbered steps are what the model is given. A person can edit a skill or add a new one as an ordinary note.

!fig figures/screens2/console-skill.png | Figure 5.5: A skill as it is stored in the vault. | 5.8

After a conversation the engine proposes up to three notes of what the person decided. A note is offered only if its quote is found in the person's own words, and it is written only when the person accepts it.

### 5.4.5 Serving Other Models and Tools

The engine is not tied to the model it hosts. Figure 5.6 shows an outside client asking Burrow to prepare a task through the Model Context Protocol. Burrow returns its decision and the excerpts without calling a model. Figure 5.7 shows Burrow used as the retriever inside a LangChain pipeline, in the place where a vector database would normally sit.

!fig figures/screens2/console-mcp.png | Figure 5.6: An outside client calling the tool `vault_prepare` through the Model Context Protocol. | 6.2

!fig figures/screens2/console-langchain.png | Figure 5.7: Burrow as the retriever in a LangChain pipeline. | 6.2

## 5.5 Experiments and Evaluation

### 5.5.1 Experimental Set-ups

The same 170 questions were put to six set-ups.

i) The on-device model alone.
ii) The on-device model with plain retrieval: the best-ranked excerpts pasted in front of the question, 12,000 characters. This is Burrow as it was before the engine's steps were built.
iii) The on-device model with a standard vector database pipeline, Chroma, using the same embedding model and the same 12,000 characters. This is the baseline.
iv) The on-device model with the Burrow engine.
v) The cloud model alone.
vi) The cloud model given the prompt that the engine prepared.

Set-ups i to iv were run with Gemma 4 12B and again with Qwen3.5 4B. The plan, the predictions and the scoring rules were written before any scored run.

### 5.5.2 Evaluation Metrics

Accuracy is the share of questions answered right, as Equation 5.1 states. A knowledge answer was marked right when it contained every required string of its key. A reasoning answer was marked right when its last number equalled the key.

!eq accuracy | Equation 5.1: Accuracy of a set-up.

The fraction of the capability gap closed is Equation 3.1, where the floor is the on-device model alone and the ceiling is the cloud model alone. Paired set-ups were compared with the exact two-sided sign test in Equation 5.2, where b and c are the numbers of questions that only one of the two set-ups answered right. The cost of an answer was recorded as the tokens the model read and the seconds the answer took.

!eq sign | Equation 5.2: Exact two-sided sign test on paired answers.

### 5.5.3 Results

Figure 5.8 and Table 5.4 give the answers right for the main model. Alone, Gemma 4 12B answered 9 of the 120 knowledge questions. With the engine it answered 102. The cloud model alone answered 40, because the material is private or recent, and 109 when it was given the same memory.

!fig figures/v2/chart-accuracy-main.png | Figure 5.8: Answers right by set-up and task type, Gemma 4 12B and the cloud model. | 6.2

!include generated2/accuracy-gemma4-12b.md

The reasoning column shows the opposite effect. Alone, the model solved 47 of 50 problems. With plain retrieval it solved 7, because excerpts that had nothing to do with the sum were placed in front of it. The engine left the vault out of all 50 and the model solved 48.

Table 5.5 gives the fraction of the gap closed. On knowledge questions the on-device model with the engine passed the cloud model alone, so the fraction is above 100%. On reasoning questions the floor and the ceiling were two questions apart, so no fraction is reported.

!include generated2/gap.md

Table 5.6 gives the cost. The engine showed the main model more of the vault than plain retrieval did, about 6,100 tokens against 3,800, and an answer took 9.2 seconds against 8.3. The engine's own work before the model started took 0.06 seconds. The engine brought back every file holding the answer on 111 of 120 questions, against 102 for plain retrieval and 95 for Chroma.

!include generated2/cost.md

The smaller model gave a mixed result, shown in Figure 5.9 and in Table A3.1 of Appendix 3. Alone, Qwen3.5 4B answered 6 of the 120 knowledge questions. With plain retrieval it answered 97 and with the engine 91, so on knowledge the engine did not improve on plain retrieval for this model (1 question gained and 7 lost, p = 0.070). On reasoning the pattern of the main model repeated more sharply: 46 of 50 alone, 9 with plain retrieval, 1 with the Chroma pipeline, and 49 with the engine.

!fig figures/v2/chart-accuracy-small.png | Figure 5.9: Answers right by set-up and task type, Qwen3.5 4B and the cloud model. | 6.2

Two parts of the engine were then switched off in turn on the main model. Without skills the engine answered 149 of the 170 questions, against 150 with them. Without the citation check it answered 151. The check asked the model again on only 1 of the 170 questions, because only 1 of the 145 places the model cited was not among what it had been shown. Neither part changed the score by more than the one-question difference that two identical runs showed. Table A3.3 in Appendix 3 gives the paired tests.

Figure 5.10 and Table 5.7 answer the question of how much to show. The engine was run again on the 120 knowledge questions with the amount shown fixed at four sizes, beside the fitted 17,417 characters. At 2,000 characters most questions received nothing, because the best piece did not fit, and 15 were answered. Accuracy then rose with every increase: 56 at 4,000 characters, 76 at 8,000, 102 at the fitted size and 112 at 32,000. The gain per token fell the whole way, from 27.9 points for each 1,000 tokens at 4,000 characters to 7.8 at 32,000, and the time for an answer rose from 2.1 to 15.6 seconds.

!fig figures/v2/chart-sweep.png | Figure 5.10: Knowledge answers right against tokens read, as the amount of the vault shown to Gemma 4 12B grows. | 5.8

!include generated2/sweep.md

Figure 5.11 shows the speed of a lookup before and after the search was rebuilt, on an index of 11,710 pieces from the Django repository. Before the rebuild a lookup that followed links took a median of 2.87 seconds and 31.5 seconds at worst. After it the median was 0.18 seconds and the worst 0.36 seconds, about sixteen times faster at the median. Plain search was already fast and stayed at about 0.15 seconds. The rebuilt search found exactly the same files as before on the 101 real bug fixes of the earlier evaluation: a changed file on 59 by search and on 72 by following links.

!fig figures/v2/chart-speed.png | Figure 5.11: Median time of one lookup on the Django index, before and after the search was rebuilt. | 5.2

### 5.5.4 A Coding Trial Against the Cloud Model

A small trial asked whether the on-device model can build something beside the cloud model. Three briefs for a single-file website were given to Gemma 4 12B and to Claude: a matatu fare splitter, a clinic queue board that survives a reload, and a landing page with a phone menu and a pricing toggle. Each page was scored in a real browser with the same fixed checks, 42 in all. Figure 5.12 shows the pages.

!fig figures/v2/web-compare.png | Figure 5.12: The same three briefs built by Gemma 4 12B alone, by Gemma with a skill and a note of known failures, and by Claude alone. | 6.3

Claude passed all 42 checks in every set-up. Gemma alone passed 41. With the brief the engine prepared, which carried a web-building skill, Gemma passed 39, because one page had a script error. With the skill and a note of known failures handed over directly, it passed 41, and the note prevented that error. The engine had left the note out, because it judged each brief to be a task to work out. The trial is three briefs run once, so it is a demonstration. It shows that the on-device model was close to the cloud model on whether a page works, that the cloud model's pages were better designed, and that the engine should fetch recorded lessons for building tasks.

## 5.6 System Testing

The engine has 212 automated tests, and all of them passed on the frozen source. Table 5.8 gives the system test cases, one or more for each requirement of Chapter 4.

!tab Table 5.8: System test cases
!widths 0.55,0.8,1.5,1.3,1.2,0.5
| Test case | Module | Description and test data | Expected result | Actual result | Pass or fail |
| TC-01 | Index (FR-01) | A vault indexed twice, then with one file changed and one removed | Nothing rebuilt the second time; old words gone the third time | As expected | Pass |
| TC-02 | Search (FR-02) | A question whose words are absent from the right file | The file is found by meaning | As expected | Pass |
| TC-03 | Search (FR-03) | A question naming only the first of three linked files | The third file is reached by following links | As expected | Pass |
| TC-04 | Decide (FR-04) | A question the vault knows nothing about | The vault is left out | Left out; the model received only the question | Pass |
| TC-05 | Decide (FR-04) | The 50 reasoning problems of Section 5.5 | The vault is left out | Left out on 50 of 50 | Pass |
| TC-06 | Skills (FR-05) | A sum, with a calculation skill and a documents skill in the vault | The calculation skill and no excerpts | As expected | Pass |
| TC-07 | Fit (FR-06) | A fast small model, a fast large model and a slow large model | 8,000, 24,000 and 6,400 characters | As expected | Pass |
| TC-08 | Answer (FR-07) | A question about a regulation, in the Mac app | An answer with the decision line and the files read | As in Figure 5.4 | Pass |
| TC-09 | Check (FR-08) | An answer citing a file it was not shown | One retry; the better grounded answer kept | As expected | Pass |
| TC-10 | Learn (FR-09) | Three proposed notes, one quoting words the person never typed | Only the two backed by the person's words offered | As expected | Pass |
| TC-11 | Outside models (FR-10) | `vault_prepare` called through MCP | The decision and excerpts, no chat model called | As in Figure 5.6 | Pass |
| TC-12 | Durability (NFR-02) | The index deleted and rebuilt | No note lost | As expected | Pass |

## 5.7 Results and Discussion

The second research question asked how much of the capability gap a frozen-weights memory engine can close. On knowledge the engine closed all of it and more. Gemma 4 12B went from 9 to 102 of 120 questions, against 40 for the cloud model alone, which is 300% of the gap by Equation 3.1. The figure is above 100% because a cloud model cannot know a private project or documents newer than its training. The fairer ceiling is the cloud model with the same memory, which answered 109. Against that ceiling the on-device model with the engine was 7 questions behind. The result agrees with Mallen et al. (2023), who found that retrieval helps most on the facts a model has not memorised. Narayan et al. (2025) measured the same gap and recovered 87% of the cloud model's performance, but by having the on-device model work with a cloud model. Burrow kept everything on the device.

The third research question asked whether memory helps knowledge more than reasoning. It does, and the experiments showed something stronger. Memory given to a reasoning task did harm: plain retrieval cut the model from 47 to 7 of 50 problems. The engine's first step removed that harm by deciding, on all 50 problems, that the vault was not needed. The harm itself is known: Shi et al. (2023) and Mirzadeh et al. (2025) showed that irrelevant sentences added to grade-school problems sharply reduce accuracy, and Cuconasu et al. (2024) showed that highly ranked passages without the answer are the most damaging kind. What this study adds is the size of the effect for a local model on GSM8K when the irrelevant text comes from the model's own memory, and a gate that removes it. This is the clearest difference between an engine and a database. A database answers every query it is given. An engine decides whether the query should be made.

The engine also beat both ways of using memory without it. Against plain retrieval it gained 10 knowledge questions and lost 2 (p = 0.039), and against the Chroma baseline it gained 34 and lost 7 (p < 0.001). The ablation shows where that gain came from. Skills and the citation check did not change the score, so the gain on knowledge came from the first two steps: deciding how to read the vault and fitting the amount shown to the model. The engine brought back every needed file on 111 questions against 102 for plain retrieval. On the smaller model, which was shown the same 12,000 characters as plain retrieval, that gain did not appear, and the engine was 6 questions behind plain retrieval on knowledge. The skill store is therefore a working feature whose benefit this evaluation did not show.

The fourth and fifth research questions concern cost. The budget sweep answers the fourth question in two parts. The gap closed per token was highest at the smallest budget that worked, 4,000 characters, and fell as more was shown. Accuracy itself did not peak inside the range tested: at 32,000 characters the on-device model answered 112 of 120, which is 3 more than the cloud model with Burrow, at 15.6 seconds an answer. The fitted budget of about 17,000 characters, which the engine chose from the model's reading speed, sits between the two at 102 right in 9.2 seconds. The budget is therefore a choice between speed and accuracy that the engine exposes, not a single best value. An engine answer took about nine seconds on the laptop, almost all of it the model reading and writing, and the engine's own share was under a tenth of a second.

The objectives were met as follows. Objective i was met by the review in Chapter 2. Objective ii was met by the design in Chapter 4, with one change: ranking by recency and importance was not built, and ranking by words, meaning and links was built in its place. Objective iii was met by the engine described in Section 5.4, which passes its 212 tests. Objectives iv and v were met by the measurements in Section 5.5.

The results have limits. The knowledge questions were written by a language model and scored by answer keys, so a right string in a wrong sentence counts as right. Each question was run once on one laptop, and other jobs shared the machine during some runs, so the times are indicative. Of the engine's 18 wrong knowledge answers, 8 had a needed file missing from what was shown and 10 had every file shown, so both retrieval and the model's reading still fail, as Joren et al. (2025) also found for small models given sufficient context. Three faults found after the engine was frozen were left unfixed so that the measured engine is the one described: the check with retry runs on the command line but not in the app or the chat, the MCP tool uses a fixed budget and not the fitted one, and the engine's own prompt does not stop an excerpt from closing its block. No person other than the developer has used the app, so its usability is not claimed.

## 5.8 GitHub Documentation

The project is kept in a public GitHub repository at https://github.com/Satasdin/CAMR, on the default branch `burrow`. Figure 5.13 shows the recent history, the tags and the folders. The engine is in `Sources`, its tests in `Tests`, the Mac app in `app`, the evaluation in `trials`, and this report with its scripts in `docs/report`.

!fig figures/screens2/console-git.png | Figure 5.13: The repository's recent history, tags and folders. | 6.0

Each evaluation was run on a tagged, frozen version. The tag `evaluation-1` marks retrieval before the engine's steps, and `evaluation-2` marks the engine measured in this chapter. The hash of the frozen program is saved in every results folder, and the harness refuses to add answers from a different program to the same folder. To reproduce the work, build with `swift build -c release`, run `swift test`, and follow `trials/gap/README.md`.
