# Appendices

## Appendix 1: Gantt Chart

Figure A1.1 shows the work plan to the end of November 2026, and Table A1.1 gives the course milestones.

!fig figures/gantt.png | Figure A1.1: Project work plan to the end of November 2026. | 6.2

!tab Table A1.1: Course milestones and their status
!widths 0.5,3.6,1.1,1
| No. | Task | Due date | Status |
| 1 | Supervisor selection and allocation | 7 May 2026 | Done |
| 2 | Document formatting and template creation | 8 May 2026 | Done |
| 3 | Topic creation and selection | - | Done |
| 4 | Abstract and Chapters 1 to 3 | - | Done |
| 5 | Proposal submission | 12 June 2026 | Done |
| 6 | Proposal oral defence | 13 to 16 July 2026 | Done |
| 7 | Proposal marking and revision | 31 July 2026 | Done |
| 8 | Chapter 4: System Analysis and Design | 17 August 2026 | Done |
| 9 | Sprint II review | 5 November 2026 | Done |
| 10 | Documentation | Date to be confirmed | In progress |
| 11 | Project final defence | 23 November 2026 | Pending |

## Appendix 2: Feedback-Resolution Matrix

Table A2.1 records the feedback received and how each item was resolved. Table A2.2 lists every change made to Chapters 1 to 3 since the approved proposal.

!tab Table A2.1: Feedback received and its resolution
!widths 1.8,0.9,1,2,0.6
| Issue | Source | Affected section | Action | Status |
| "Very hard to understand" | Sprint II review, 5 Nov 2026 | 1.2, 4.4 | The engine was rebuilt around plain files and five named steps, and the report describes it in standard terms | Done |
| "Just a report of benchmarks" | Sprint II review | 1.6, 5.3 | A usable app, a terminal chat and an MCP server were built around the engine; the scope now includes them | Done |
| Show it working with native Ollama models | Sprint II review | 5.2, 5.3 | Ollama is the only model runner; every local result was produced through it | Done |
| The person cannot create or remove their own collections | Sprint II review | 4.4 | The memory is the person's own folder of files; nothing is seeded | Done |
| Model activity should be visible | Sprint II review | 5.3.1 | The app states what the engine decided, the method used and the files read under each answer | Done |
| Can it generate reports natively? | Sprint II review | 5.3.1 | An answer can be kept as a note; no report format was built | Partly |
| If it codes, let it code, with live previews | Sprint II review | 1.6 | The app proposes changes to files for acceptance; live previews were not built | Partly |
| [PENDING: written proposal comments and defence feedback.] | Proposal defence | - | - | Open |

!include chapters3/changes-table.md

## Appendix 3: Further Results

The tables below support Section 5.5. Table A3.1 gives the small model, Table A3.2 the main model by subject, Table A3.3 the paired tests, Tables A3.4 and A3.5 what the engine decided, Table A3.6 where the wrong answers came from, and Table A3.7 one question of each kind. Every answer is saved in the repository under `trials/results/gap-1`, and the full record of the 212 automated tests is in `unit-tests-evaluation-2.log` in the same folder.

!include generated2/accuracy-qwen3.5-4b.md

!include generated2/subjects.md

!include generated2/sign.md

!include generated2/decisions.md

!include generated2/wrong.md

!include generated2/examples.md

Before the engine's five steps were built, retrieval alone was tested at tag `evaluation-1`. On 101 real bug fixes from four public repositories, following links reached a changed file on 72 and plain search on 59 (p = 0.002). On three held-back synthetic projects worked by simulated developer agents, memory did not measurably help the small model write working code. Those results are saved under `trials/results` and led to the engine described in this report.

## Appendix 4: Requirements Traceability

Table A4.1 traces each requirement to the part that implements it and the test that verifies it.

!tab Table A4.1: Traceability from requirement to component and test
!widths 0.8,0.8,2.2,1.2,1.3
| Requirement | Objective | Component | Test case | Result |
| FR-01 | iii | `Vault`, `Scanner`, `Chunker` | TC-01 | Pass |
| FR-02 | ii, iii | `Retrieval`, `Index` | TC-02 | Pass |
| FR-03 | ii, iii | `Retrieval` | TC-03 | Pass |
| FR-04 | ii | `Engine.brief` | TC-04, TC-05 | Pass |
| FR-05 | ii | `Skills`, `Engine.brief` | TC-06 | Pass |
| FR-06 | ii, v | `Fit` | TC-07 | Pass |
| FR-07 | iii | `Engine.engage`, `Asking` | TC-08 | Pass |
| FR-08 | ii | `Engine.engage` | TC-09 | Pass on the command line only |
| FR-09 | ii | `Engine.lessons`, `keep` | TC-10 | Pass |
| FR-10 | iii | `Engine.brief`, `BurrowMCP` | TC-11 | Pass |
| NFR-01 | iii | `Ollama` | Inspection | Pass |
| NFR-02 | iii | Rebuildable index | TC-12 | Pass |
| NFR-03 | iii | `Asking`, `ProjectContent` | Automated tests | Pass on the tools path |
| NFR-04 | iv | Harness | Table 5.6 | Pass |
| NFR-05 | iii | `Database` | Inspection | Pass |
| NFR-06 | iii | Swift package | 212 automated tests | Pass on one machine |

## Appendix 5: User Guide

**What is needed.** A Mac with Xcode and Ollama. Pull the models with `ollama pull gemma4:12b` and `ollama pull qwen3-embedding:0.6b`.

**Building.** Run `swift build -c release` in the project folder for the command-line tool, and `app/build.sh` for the app. Open `app/build/Burrow.app`.

**Using the app.**

i) Choose a folder as the vault. An existing Obsidian vault works as it is.
ii) Write notes in the centre pane, and link notes with `[[`.
iii) To add code, choose Add, then Link a Folder.
iv) Open Ask and type a question. Under the answer the app shows what the engine decided, the method it used and the files it read.
v) To have a change proposed, use the change option beside the question field. Review it, then choose Accept or Reject.

**Using the terminal.**

i) `burrow index <vault> --vault` builds the index.
ii) `burrow fit <vault> --vault --model gemma4:12b` measures the model once.
iii) `burrow skills <vault> --vault --install` adds the starter skills to the vault's `Skills` folder. Edit them or add new ones as Markdown files with a `when:` line.
iv) `burrow ask <vault> "question" --mode engine --model gemma4:12b --vault` answers through the engine.
v) `burrow chat <vault>` opens a chat. `/keep` proposes notes from the conversation and asks before writing each one.

**Using Burrow from another model or tool.** `burrow brief <vault> "task" --vault --json` returns the prepared prompt for any model. For an MCP client, point it at the built program with the arguments `mcp` and the full path of the vault, and call `vault_prepare`. A client that is a cloud service sends what it reads to that service.

**Known limitations.** Burrow runs on macOS only. The check with retry runs on `burrow ask`; the app only warns. An empty question and a missing folder are not rejected.

## Appendix 6: More Screens of the App

!fig figures/screens/note.png | Figure A6.1: A note being edited, with its links and properties. | 6.2

!fig figures/screens/graph.png | Figure A6.2: The graph of a vault, coloured by folder. | 6.2

!fig figures/screens/reading.png | Figure A6.3: A note in the reading view. | 6.2

## Appendix 7: AI-Use Log

Table A7.1 is the AI-use log. Full prompts and replies are retained in the Claude Code session transcripts on the development Mac. [PENDING: the student to add AI use before 9 November and to confirm this log.]

!tab Table A7.1: AI-use log
!widths 0.7,0.95,1.6,1.3,1.65
| Date (2026) | Tool and model | Used for | Retained output | Corrections and verification |
| 9 Nov | Claude Code | Plan and scope of Burrow, written with the student | Plan and `DECISIONS.md` | Reviewed and approved by the student |
| 9 Nov | Claude Code | Engine, command line, agent test harness | Source and tests | `swift test` |
| 9-10 Nov | Claude Code | Mac app, terminal view, chat and MCP server | Source and tests | `swift test`; screens reviewed by the student |
| 10 Nov | Claude Code | The earlier evaluation: held-back projects and real bug fixes | Code, projects, results | Plan written before scoring; results saved once |
| 10 Nov | Claude Code | The engine's five steps, skills and faster search, at the student's direction | Source, tests, `DECISIONS.md` D-50 to D-58 | 212 tests; thresholds set on development questions only |
| 10 Nov | Claude Code agents | Curated documents and questions; evaluation harness; vector database baseline | `trials/gap` | Checker scripts; fixture run; plan written before scoring |
| 10 Nov | Claude (`claude-sonnet-5-5`) through the API | The cloud model in the experiments | Saved answers | Scored by fixed answer keys |
| 10 Nov | Claude Code agents | Chapters 1 to 5 rewritten on the layout of earlier graduates' reports; a verified source pack; diagrams; tables and charts from saved results | Report and generators in `docs/report` | Each source confirmed at its published page; each change from the proposal listed in Table A2.2; tables generated by script |
| [PENDING] | - | The student's own review and edits of this report | - | - |

## Appendix 8: Similarity Report

[PENDING: attach the one-page similarity report.]
