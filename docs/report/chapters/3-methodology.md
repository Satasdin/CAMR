# Chapter 3:  Methodology

## 3.1 Introduction

This chapter presents the methodological approach of the study. Burrow is a software system whose central claims concern how well a language model is supported by retrieved memory, so the project combined two strands. An experimental research paradigm governed how those claims were tested, and an Agile prototyping methodology governed how the system was built. The development paradigm was Object-Oriented Analysis and Design (OOAD), which determined the diagrams presented in Chapter 4.

Section 3.2 sets out the research paradigm together with data acquisition, data processing, model selection and validation. Section 3.3 presents the system development methodology and its justification. Section 3.4 presents the methodology diagram and explains how each stage was applied. Sections 3.5 and 3.6 give the deliverables and the tools and techniques.

## 3.2 Research Paradigm

The project adopted an experimental research paradigm, in which a hypothesis is tested by controlled comparison. The hypothesis stated in Section 1.1 was tested by giving the same local model the same material under three memory conditions, and by holding constant everything that was not the condition under study. Measurable objectives were defined first, in the form of the research questions in Section 1.4. Data was then acquired and prepared, the retrieval system and its settings were tuned on development material only, and a final version was frozen before any held-back material was scored.

Figure 3.1 shows this procedure. The rule that separates it from informal testing is the freeze. Tuning was permitted only on the tuning project, the code was tagged `evaluation-1` before any held-back project or real repository was run, the plan was written down in advance (`docs/report/evaluation-plan.md`, decision D-49), and each held-back project was scored once. A fault found in the engine during scoring was reported and was not fixed in place.

!fig figures/procedure.png | Figure 3.1: The build, tune, freeze and score procedure followed in this study. | 6.2

Table 3.1 defines the three conditions. All three were implemented in one engine, so that the comparison measured the code that ships (D-13).

!tab Table 3.1: Conditions compared in the evaluation
!widths 1.2,3.1,1.9
| Condition | What the model receives | Purpose |
| None | The task or question alone, and any files it asks to open | Baseline: a local model with no lasting memory |
| Search | The best pieces of files by word and meaning search, with no links followed | Baseline: standard retrieval over the same notes and code |
| Walk | The same starting pieces, then pieces reached by following links for up to two hops | The approach under study |

Four controls kept the comparison fair. Every condition was held to the same upper limit of 12,000 characters of excerpts (D-7). Walk fills that limit more fully than search does, as Section 5.4.4 reports, and this is treated as a threat to validity in Section 5.7.9. Every condition had the same allowance of three rounds of opening files (D-18). Each session began from correct code, made of the starting code plus the correct solutions of earlier sessions, so that one failure could not cause later failures (D-17). Notes were written from the brief alone, so that they were identical for search and walk and those two conditions differed only in retrieval (D-19).

### 3.2.1 Data Acquisition

Three kinds of data were used. None of them was collected from people.

**Synthetic test projects.** Four software projects were written for the evaluation: `courier` for tuning, and `sacco`, `clinic` and `matatu` as held-back projects. Each is a folder holding starting code, session briefs, hidden tests and correct solutions. They were authored by AI agents and are declared in Section 5.6 (D-14). The held-back projects were written after the engine was frozen, by agents instructed not to read the retrieval code. Table 3.2 shows the fields of one session, using the real `sacco` session 05.

!tab Table 3.2: Example contents of one test session (sacco, session 05)
!widths 1.5,4.7
| Field | Content |
| Identifier and category | 05, depends: the task needs a decision established in an earlier session |
| Brief given to the agent | `member_statement` in `sacco/statements/member.py` must return a new key, `reversed_count`: how many postings were undone during the period, or `0` if there were none. |
| Hidden task tests | `tests/test_task.py`, run after the session and never shown to the agent |
| Hidden decision tests | `tests/test_decisions.py`, which fail if the earlier decision has been broken |
| Correct solution | `reference/`, which must pass every test |
| Tempting wrong fix | `trap/`, which must fail the decision tests by an assertion and not by a crash |

**Real repositories and issues.** Real bug fixes were taken from the test split of SWE-bench (Jimenez et al., 2024), which pairs GitHub issues with the commit before their fix; 2,294 records were retrieved. Four repositories were chosen by size before any result was seen: `psf/requests`, `pallets/flask`, `pytest-dev/pytest` and `django/django`. For each, the latest 30 instances by date were used, or all of them where fewer existed, which gave 101 instances. Table 3.3 shows the fields used from one real record.

!tab Table 3.3: Example contents of one SWE-bench record (pallets__flask-4045)
!widths 1.5,4.7
| Field | Use in this study |
| `instance_id` | Identifier of the record |
| `base_commit` | The repository was checked out here, before the fix |
| `problem_statement` | The issue text, used unchanged as the question |
| `patch` | The fix. Its changed source files form the correct set; here `src/flask/blueprints.py` |
| `test_patch`, `FAIL_TO_PASS` | Not used, because the test measures retrieval and does not attempt the fix |

**The person's own notes and code.** In ordinary use Burrow reads a person's own vault on their own Mac. No such material was collected for this study. The figures in Chapter 5 were captured on a demonstration vault.

**Privacy and permissions.** No personal data was deliberately collected and no human participants took part. The four public repositories are published under open-source licences (Section 5.3.2), and only their identifiers and file paths are reproduced in this report. Simulated developer agents are always described as such, because participants must not be fabricated.

### 3.2.2 Data Processing

Repository content and notes passed through the same preparation.

**Cleaning.** Only text files with recognised extensions were read. Inside a Git repository the file list came from Git, so that ignored files stayed out. Hidden folders, dependency folders and build output were skipped. Files larger than 1 MB were left out, as were JSON, XML, YAML and text files larger than 32 KB, because on the first real repository tried, results files made up about 90% of the pieces and overwhelmed the code (D-9). For SWE-bench, the correct set was restricted to source files that existed before the fix; no instance had to be dropped for containing only new files.

**Transformation.** Each file was cut into pieces of about 45 lines and at most 80 lines or 3,000 characters, preferring the start of a declaration and then a blank line, so that a function usually stayed whole (D-46). Compound names were split for word search, so that `parseUserToken` could also be found through `parse`, `user` and `token`. Each piece was stored for full-text search and, when Ollama was available, given a vector by the embedding model. Links were extracted from imports, uses of defined names, wiki and Markdown links, and notes that name code.

**Augmentation.** No augmentation was applied. Class balance did not arise as a question, because no model was trained; the session categories were fixed by design, as described in Section 3.2.4.

### 3.2.3 Model Training

No language model was trained or fine-tuned in this study, and no model weights changed. Burrow is a retrieval system placed in front of pre-trained models, so this stage consisted of selecting models and configuring retrieval and prompts on development material.

The primary chat model was `qwen3:4b-instruct-2507-q4_K_M`. It was selected because, on a question about a real repository, `qwen3:4b` reasoned for 97 to 197 seconds even with thinking switched off while the instruct build answered in 4 to 6 seconds (D-11). That was one question, so it was a working choice and not a finding. `qwen3:1.7b` and `qwen3:8b` were secondary models, and `qwen3-embedding:0.6b` supplied vectors. Every call used temperature 0, seed 7 and a limit of 2,048 generated tokens. Questions used a context of 8,192 tokens; the agent test, the terminal chat and change requests in the app used 16,384.

The retrieval settings were 12,000 characters per question, four entry files, two hops, 3,000 characters per excerpt, and the rank fusion constant of 60. Only the prompt rule on unrecorded reasons (D-48) and the ranking of tests and run output (D-45) were adjusted using measured checks, and these were adjusted on the tuning project and on Burrow's own repository. Earlier design rules arose from other development repositories, namely the exact-name rule (D-12) and the exclusion of large data files (D-9), and none of those repositories was scored. The other values were single working choices and were not tuned systematically.

### 3.2.4 Model Validation and Testing

Sessions were placed in four categories (D-16). Setup sessions establish a decision and are not scored. Depends sessions need an earlier decision. Plain sessions need no memory and act as a control. Unknown sessions ask about something never recorded, where the correct response is to say that it is not known. Each held-back project had 2 setup, 1 plain, 3 depends and 2 unknown sessions, which gave 6 scored sessions per project and 18 per cell. No part of the held-back material appeared in tuning.

Before any model ran, a project had to pass a verification step: the correct solution passes, the code before each task fails its tests, each tempting wrong fix fails the decision tests by a failed assertion and not a crash, and the final code passes every session's tests (D-15). Code written by a model ran under `sandbox-exec` with no network access, no writes outside the scratch folder and a 20-second limit (D-21).

Table 3.4 lists the measures and the research question that each serves. Recall on a real fix is defined by Equation 3.1, where the set G holds the files changed by the real fix for instance i and the set F holds the files retrieved for it under mode m.

!eq recall | Equation 3.1: Recall of the changed files for one instance.

Search and walk were compared with an exact two-sided sign test on the instances where they disagreed, as in Equation 3.2, where b is the number of instances on which walk was better and c the number on which search was better. The test makes no assumption about the size of a difference, which suits a yes-or-no outcome per instance. For paired binary outcomes it gives the same result as the exact form of the McNemar test, which Dror et al. (2018) recommend for such data. Smucker et al. (2007) advise against the sign test for comparing mean scores, so it was applied only to the yes-or-no measures, and mean recall is reported without a test. The plan named the test and did not fix a significance level. This report reads p below 0.05 as significant, following convention, and always states the exact value.

!eq sign | Equation 3.2: Exact two-sided sign test.

!tab Table 3.4: Measures and the research question each serves
!widths 2.3,2.6,1.3
| Measure | How it was obtained | Research question |
| Each required function works | Automated test case per requirement, application checks and a clean install | v(a) |
| Later tasks passed | Hidden tests run after the session | v(b) |
| Earlier decisions broken | Decision tests run after the session, counted only on a failed assertion (D-20) | v(b) |
| Says it does not know when nothing was recorded | Pattern check on the answer to an unknown session | v(b) |
| Files read and seconds taken | Recorded by the test harness | v(b) |
| Right file first, any changed file reached, every changed file reached, mean recall | Past bug fixes in real repositories, each mode held to 12,000 characters | v(c) |
| Index size, retrieval time and answer time | Four repositories of increasing size | v(d) |

**Explainability and human oversight.** Every excerpt carries the reason it was read, and every answer is required to name the files and lines used, so a person can check an answer against its source. No model output changes a file by itself: a proposed change is written only when a person accepts it and only if the file has not changed in the meantime. The sequence is that a person asks, the model proposes, the person reviews and approves or rejects, and only then is anything written.

**Simulated developer agents.** Human participants could not be obtained in the time available, because the classmates who might have taken part were not available. Tasks were therefore carried out by simulated developer agents: a local model given a task brief in a loop that lets it open files and write changes. These agents are software. They are not participants, and the results they produce say nothing direct about human users. Agnew et al. (2024) caution that substituting language models for human participants can undermine the values that human-subject research protects, and Gerosa et al. (2024) conclude that AI cannot fully replace human subjects in software engineering research. The agent test is therefore reported as a controlled check of the mechanism and not as a user study.

## 3.3 System Development Methodology

The system was developed using an Agile prototyping methodology, in which a working prototype is built early and refined in short cycles. Scrum's review cycle was borrowed through the course's sprint reviews, while its team roles were not used, because the project had one developer. Each change was built, checked by automated tests and tried on a real folder, and each design choice was recorded in a numbered decision log, `DECISIONS.md`, so that it could be traced and defended. This report cites those entries as D-1 to D-49.

### 3.3.1 Justification of the Methodology

Agile prototyping was selected for three reasons rooted in the nature of the system. First, the behaviour of a language model working from retrieved context could not be fixed in advance. Whether a retrieval rule helps can only be seen by running it, so working software had to come before detailed specification, and Martínez-Fernández et al. (2022) identify the experimental nature of AI-based systems as a recurring concern in their software engineering. This is the priority set out in the Manifesto for Agile Software Development (Beck et al., 2001), and it matches the empirical process of inspection and adaptation described in the Scrum Guide (Schwaber & Sutherland, 2020).

Second, prototyping suits requirements that are uncertain until people or tests have exercised a working system. Sommerville (2016) describes a process of establishing prototype objectives, defining functionality, developing the prototype and evaluating it, and that sequence fits a project in which an early version is expected to expose what the requirements should have been. It proved necessary here: a change of direction occurred in the middle of the project, and it would have been expensive under a phased process.

Third, the chosen development paradigm supports the methodology. OOAD models a system as objects with clear responsibilities, and those objects can be built and tested one at a time, which aligns OOAD with incremental delivery (Tegarden et al., 2025). Burrow's engine is built from such types, including a vault, a retriever and a database connection. Structured analysis, by contrast, works best where data flows can be settled before implementation and is better paired with phased methods, which did not describe this project.

A Modified Waterfall approach was rejected because the requirements changed, and the fixed phases would have made that change costly. Full Scrum was rejected because roles such as product owner and development team could not be meaningfully separated in a one-person project.

## 3.4 Methodology Diagram

Figure 3.2 presents the prototype development process used, adapted from Sommerville (2016). The figure has been redrawn for this report, and the iteration path has been added to reflect the Agile refinement cycle.

!fig figures/methodology.png | Figure 3.2: Prototype development process. Adapted from Sommerville (2016). | 6.2

### 3.4.1 Prototype Planning

The first stage established the user need and the scope of the prototype. Requirements were drawn from secondary sources, namely the studies of developer concerns and memory systems reviewed in Chapter 2, and from direct feedback from the course lecturer at the Sprint II review of 5 November 2026.

An earlier prototype named CAMR had saved a model's internal state on disk for reuse, and it was the subject of the approved proposal. At the Sprint II review the lecturer found the system difficult to understand and observed that it read as a report of benchmarks and not as a product. The project was restarted on 9 November 2026 as Burrow, with new code and with plain files as the memory. No CAMR result is claimed for Burrow, and Burrow's numbers were measured from zero. On 10 November 2026 the scope widened from software projects alone to a vault for any notes, with code folders linked in and questions limited to one folder when wanted (D-40). [PENDING: record the supervisor's approval of the change of topic and title.]

The prototype's priorities followed from the problem. It had to show that a person's notes and code could be kept private on one machine, that a local model could answer from them and name its sources, and that the retrieval could be measured against simple baselines. Those functions came first because the research questions could not be examined without them.

### 3.4.2 Initial Prototype Development

The first version implemented the core path from files to answer: scanning, cutting into pieces, the full-text index, the three retrieval modes, and an answer through Ollama, reachable from a command-line program. The design followed OOAD, so the analysis and design were expressed in Unified Modeling Language: use case, activity, sequence, class and state machine diagrams, together with a logical database schema, a system architecture and interface wireframes. These are presented in Chapter 4. Swift was used for the engine and every interface, so that no second language had to be installed by another person (D-1). The tools are justified in Section 3.6.

### 3.4.3 Iterative Refinement

The course's three development sprints concerned the earlier prototype. Burrow itself was built in short cycles across 9 and 10 November 2026. Each cycle added or changed one capability, ran the full automated test suite, and tried the result on a real folder. After the core was working, the cycles added the agent test harness, the Mac app, the terminal view, the terminal chat and the Model Context Protocol server. Faults found by use changed the design. For example, the discovery that a note about text budgets had been linked to a pricing file through an everyday word led to the rule that such a word links only when written as code (D-25), and the discovery that test files were ranked above the code they test led to a lower ranking for them (D-45). Each such change was logged with its evidence, and failed results were retained.

### 3.4.4 Testing

Testing was carried out at several levels, because each answers a different question. Unit testing, using XCTest, verified individual components such as the chunker and the link finder. Integration testing verified that components work together, for example that the Model Context Protocol server returns correct results from the real tools. System testing ran the release program end to end on a real folder. Black-box checks treated the program as a user would, through its command line. White-box tests were written with knowledge of the internals, for example to confirm that every line of a file lands in exactly one piece.

User acceptance testing could not be carried out, because no participants were available, and this is stated as a limitation in Section 5.7.9. In its place, simulated developer agents exercised the complete system against the two baselines, and this is reported as a check of the mechanism only. Performance was evaluated through task pass rates, recall of changed files, abstention on unanswerable questions, index size and time. This combination suits Agile prototyping because fast automated tests can be rerun in every cycle, while the slower and costlier evaluation is reserved for a frozen version.

### 3.4.5 Final Prototype Evaluation

The final stage evaluated the frozen prototype against the objectives. Results were saved in `trials/results`, and an agent run refuses to overwrite an existing results folder (D-23). Success was judged against the criteria set out in Section 5.4.1, and feedback was recorded in the matrix in Appendix 2. The results determine what can be claimed about the prototype and are reported, with their limits, in Section 5.7.

## 3.5 Deliverables

The project produced the following outputs:

i) The Burrow Mac application, with a note editor, reading view, graph and Ask panel.
ii) The `burrow` terminal program, with its full-screen view, chat and Model Context Protocol server.
iii) The `burrow-trial` agent test harness, four test projects and the saved results of every run.
iv) The decision log, with entries D-1 to D-49.
v) This report, including the user guide in Appendix 4.

## 3.6 Tools and Techniques

Table 3.5 lists the tools and techniques used throughout development and the reason for each.

!tab Table 3.5: Tools and techniques, and why each was selected
!widths 1.7,4.5
| Tool or technique | Reason for selection |
| Swift and SwiftUI | One language for the engine, app, terminal view and tests, with nothing else for another person to install (D-1) |
| SQLite with FTS5 | A single-file database with built-in full-text search, already present on macOS |
| Ollama | Runs local models behind one local HTTP interface, so any installed model can be used |
| Qwen3 models | Available in several sizes in Ollama, under an open licence (D-11) |
| qwen3-embedding:0.6b | A small local embedding model for meaning search |
| BM25 and reciprocal rank fusion | BM25 finds exact names and reciprocal rank fusion merges rankings using ranks alone, so no labelled data is needed to tune it (D-3) |
| Model Context Protocol | An open protocol that allows other assistants to use the vault as a set of tools |
| XCTest | Automated unit and integration tests through `swift test` |
| `sandbox-exec` | Confines code written by a model during the agent test (D-21) |
| Git | Version history for code, decisions and test results |
| Python with matplotlib | Runs hidden tests for the agent projects and draws the diagrams and result charts from saved data, keeping an editable source |
| Claude Code | AI assistance, declared in Section 5.6 |
