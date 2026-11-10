# Appendices

## Appendix 1: Gantt Chart

Figure A1.1 shows the work plan up to the end of November 2026, and Table A1.1 gives the course milestones.

!fig figures/gantt.png | Figure A1.1: Project work plan to the end of November 2026. | 6.2

!tab Table A1.1: Course milestones and their status
!widths 0.5,3.6,1.1,1
| No. | Task | Due date | Status |
| 1 | Supervisor selection and allocation | 7 May 2026 | Done |
| 2 | Document formatting and template creation | 8 May 2026 | Done |
| 3 | Topic creation and selection | - | Done; topic changed in November (Section 3.4.1) |
| 4 | Abstract | - | Done |
| 5 | Chapter 1: Introduction | - | Done |
| 6 | Chapter 2: Literature Review | - | Done |
| 7 | Chapter 3: Methodology | - | Done |
| 8 | Proposal submission | 12 June 2026 | Done |
| 9 | Proposal marking and revision | 31 July 2026 | Done |
| 10 | Proposal oral defence | 13 to 16 July 2026 | Done |
| 11 | Chapter 4: System Analysis and Design | 17 August 2026 | Done |
| 12 | Documentation progress | - | In progress |
| 13 | Documentation due | Date to be confirmed | Pending |
| 14 | Project final defence | 23 November 2026 | Pending |

## Appendix 2: Feedback-Resolution Matrix

Table A2.1 records the feedback received and how each item was resolved.

!tab Table A2.1: Feedback received and its resolution
!widths 1.8,0.9,1,2,0.6
| Issue | Source | Affected section | Action | Status |
| "Very hard to understand" | Sprint II review, 5 Nov 2026 | 1.1, 4.1 | Project restated in standard terms: notes, links and retrieval | Done |
| "Just a report of benchmarks" | Sprint II review | 5.3.1 | A usable app leads; tests support it | Done |
| Show it working with native Ollama models | Sprint II review | 5.3.1 | Ollama is the only model runtime; terminal chat added | Done |
| User cannot create or remove their own collections | Sprint II review | 4.2.1 | The vault is the person's own folder; nothing is seeded | Done |
| Model activity should be ambient | Sprint II review | 5.3.1 | The graph brightens the files read during an answer | Done |
| Can it generate reports natively? | Sprint II review | 4.3.1 | An answer can be kept as a note; no report format was built | Partly |
| If it codes, let it code, with live previews | Sprint II review | 1.6, 4.4.4 | It proposes changes for acceptance; live previews were not built | Partly |
| [PENDING: add written proposal comments and defence feedback.] | Proposal defence | - | - | Open |

## Appendix 3: Requirements Traceability

Table A3.1 traces each requirement, and Table A3.2 traces each objective to its result.

!tab Table A3.1: Traceability from objective to requirement, feature, diagram and test
!widths 0.7,0.7,1.7,1,1.1,1
| Requirement | Objective | Feature or component | Diagram | Test | Result |
| FR-01 | iv | `Vault`, `Scanner` | 4.1, 4.6 | TC-01, TC-33 | Pass, except TC-33 |
| FR-02 | iv | Note operations in `Graph.swift`; editor | 4.1, 4.12 | TC-02 | Partial: editing and deleting not covered by a test |
| FR-03 | iv | Linked folders | 4.1, 4.6 | TC-03 | Pass |
| FR-04 | iv, v(d) | `Vault.refresh` | 4.2 | TC-04 | Pass |
| FR-05 | iv | `LinkFinder` | 4.2, 4.10 | TC-05, TC-06 | Pass |
| FR-06 | iv, v(c) | Retrieval | 4.3, 4.4 | TC-07, TC-08, TC-32 | Pass |
| FR-07 | iv, v(b) | `Asking`, Ask page | 4.3, 4.4, 4.13 | TC-09, TC-27 to TC-29, TC-31 | Pass, except TC-31 |
| FR-08 | iv | Folder limit | 4.1, 4.13 | TC-10 | Pass |
| FR-09 | v(b), v(c) | `Mode`, `Budget` | 4.3, 4.8 | TC-11, TC-12 | Pass |
| FR-10 | iv | `applyChange`, change review | 4.5, 4.9, 4.13 | TC-24 | Pass |
| FR-11 | iv | `addNote`, Keep as Note | 4.1, 4.11 | TC-13 | Pass |
| FR-12 | iv | Graph page | 4.14 | TC-25 | Not tested by hand |
| FR-13 | iv | `BurrowTUI` | 4.7, 4.15 | TC-14 | Pass |
| FR-14 | iv | `BurrowChat` | 4.7 | TC-15 | Pass |
| FR-15 | iv | `BurrowMCP`, `BurrowTools` | 4.1, 4.7 | TC-16 | Pass |
| NFR-01 | iv | Ollama client | 4.7, 4.16 | Inspection | Pass |
| NFR-02 | iv | Disposable index | 4.10 | TC-17 | Pass |
| NFR-03 | iv | Marked excerpts | 4.4 | TC-18, TC-30, TC-31 | Pass, except TC-31 |
| NFR-04 | iv | `VaultTools` | 4.7 | TC-19 | Pass |
| NFR-05 | iv | One lock per connection | 4.8 | TC-20 | Pass |
| NFR-06 | iv | Cell grid | 4.15 | TC-21 | Pass |
| NFR-07 | v(a) | README | - | TC-26 | One Mac only |
| NFR-08 | v(b), v(c) | `Budget` | 4.8 | TC-11 | Pass |
| NFR-09 | v(d) | `trials/real/run.py` | - | Table 5.18 | Reported |
| NFR-10 | iv | `BurrowTUI` | 4.15 | TC-14 | Pass |
| NFR-11 | v(a) | `swift test` | - | Inspection | Pass |
| DR-01 | iv | Plain Markdown | 4.6 | TC-13 | Pass |
| DR-02 | iv | Index version | 4.2 | TC-23 | Pass |
| DR-03 | iv | `Chunker` | 4.2 | TC-22 | Pass |
| DR-04 | iv | `Scanner` | 4.2 | TC-22 | Pass |
| DR-05 | iv | `.burrow` store | 4.10, 4.16 | TC-17 | Pass |
| DR-06 | v(b) | `project.json` split | 3.1 | Inspection | Pass |
| DR-07 | v(b) | Results folders | 3.1 | Inspection | Pass for agent runs; not enforced by the real-repository harness |
| IR-01 | iv | Ollama client | 4.16 | Inspection | Pass |
| IR-02 | iv | `BurrowMCP` | 4.16 | TC-16 | Pass |
| IR-03 | iv | Fallback to words | 4.2, 4.3 | `testSearchFallsBackToWordsIfOllamaIsDown`, TC-34 | Pass |
| IR-04 | iv | `BurrowMCP` | 4.7 | TC-16 | Pass |
| IR-05 | iv | Mac app | 4.12 to 4.14 | TC-25 | Not tested by hand |
| IR-06 | iv | `BurrowTUI` | 4.15 | TC-14 | Pass |

!tab Table A3.2: Traceability from objective to result
!widths 2,1.2,1.3,1.7
| Objective | Component | Evidence | Result |
| i to iii. Current state, existing systems, gaps | Literature review | Chapter 2 | Six gaps identified |
| iv. Design and develop Burrow | All | Chapters 4 and 5 | All 15 functional requirements implemented; 31 of 39 requirements verified without qualification |
| v(a). Each function works | All | Table 5.7, Appendix 5 | 29 of 34 cases passed; 2 failed, 2 partial, 1 not tested |
| v(b). Memory across sessions | `BurrowCore`, `BurrowTrial` | Tables 5.11 to 5.14, Appendix 6 | Not shown: 5, 5 and 6 of 18 |
| v(c). Reaching the right code | Retrieval | Tables 5.15 to 5.17, Appendix 7 | Walk 72, search 59, p = 0.002; 0 notes indexed |
| v(d). Size and speed | `Vault`, `Database` | Table 5.18 | Index 2.3 to 4.4 times the code; walk slower than search |

## Appendix 4: User Guide

**What is needed.** A Mac with Xcode and with Ollama installed. The default models are pulled with `ollama pull qwen3:4b-instruct-2507-q4_K_M` and `ollama pull qwen3-embedding:0.6b`.

**Building.** Run `swift build -c release` in the project folder for the terminal program, and `app/build.sh` for the app. Open `app/build/Burrow.app`.

**Using the app.**

i) Choose a folder as the vault. An existing Obsidian vault works as it is.
ii) Write notes in the centre pane, and link notes with `[[`.
iii) To add code, choose Add, then Link a Folder. Files in the folder change only if a proposed change is accepted.
iv) Open Ask, type a question and optionally choose one folder. The files read appear before the answer.
v) To have a change proposed, use the change option beside the question field. Review it, then choose Accept or Reject.
vi) Open the graph to see files and links.

**Using the terminal.** Run `burrow link <vault> <code-folder>` once per folder, then `burrow index <vault> --vault`. `burrow tui <vault>` opens the full-screen view, where `?` lists every key, and `burrow chat <vault> --folder <name>` opens a chat with a local model.

**Connecting an MCP client.** Point the client at the built program with the arguments `mcp` and the full path of the vault. A client that is a cloud service sends what it reads to that service.

**Known limitations.** Burrow runs on macOS only. An empty question and a missing folder are not rejected (DEF-09, DEF-10). A very long question produces a misleading message about the model (DEF-08). A code folder held in iCloud Drive must be downloaded before it can be indexed.

## Appendix 5: Automated Test Record

Table A5.1 lists every automated test with its result from the clean clone of the tag `evaluation-1`. The full log is saved as `trials/results/unit-tests-evaluation-1.log`.

!include generated/tests.md

## Appendix 6: Held-Back Session Results

Tables A6.1 to A6.3 show each held-back session for each model and memory condition. Setup sessions are shown and were not scored. A dash means that the task failed and none of the other marks applied.

!include generated/held.md

## Appendix 7: Real Bug-Fix Instances

Table A7.1 lists every instance used in the real-repository test.

!include generated/real.md

## Appendix 8: AI-Use Log

Table A8.1 is the AI-use log for Burrow. Full prompts, iterations and replies are retained in the Claude Code session transcripts on the development Mac. [PENDING: the student to add AI use before 9 November and the model names for that period.]

!tab Table A8.1: AI-use log
!widths 0.7,0.95,1.6,1.3,1.65
| Date (2026) | Tool and model | Used for | Retained output | Corrections and verification |
| 9 Nov | Claude Code | Plan and scope of Burrow, written with the student | Plan and `DECISIONS.md` | Reviewed and approved by the student |
| 9 Nov | Claude Code | Engine, command line, agent test harness, the `courier` project | Source, tests, project | `swift test`; `burrow-trial verify`, 29 checks |
| 9-10 Nov | Claude Code | Mac app, terminal view, chat and MCP server | Source and tests | `swift test`; running the app; screenshots reviewed by the student |
| 10 Nov | Claude Code, Claude Opus 5.5 | Search fix, D-45 to D-47 | Code and tests | 181 tests pass; tuning check before and after |
| 10 Nov | Claude Code, Claude Opus 5.5 | D-48, the three held-back projects, the real-repository test and scoring | Code, projects, results | `burrow-trial verify`, 37 checks per project; plan written before scoring; results saved once |
| 10 Nov | Claude Code, Claude Opus 5.5 | Diagrams, charts and the drafts of this report; a search for sources | Report, generators in `docs/report` | Tables and charts generated from saved results; each source confirmed against its published record by an AI agent; the report checked against the course guide |
| [PENDING] | - | The student's own review and edits of this report | - | - |

## Appendix 9: Similarity Report

[PENDING: attach the one-page similarity report.]
