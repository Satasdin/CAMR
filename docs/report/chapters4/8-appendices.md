!landscape
# Appendices

## Appendix 1: Gantt Chart

Figure A1.1 shows the work carried out from March to November 2026, by workstream, with the course milestones, and Table A1.1 gives the milestones with their status. CAMR and Engram are earlier working names of the engine.

!fig figures/gantt.png | Figure A1.1: Project work plan, March to November 2026 | 9.7

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
| 10 | Documentation | November 2026 | In progress |
| 11 | Project final defence | 23 November 2026 | Pending |

## Appendix 2: Feedback-Resolution Matrix

Table A2.1 records the feedback received and how each item was resolved. Table A2.2 lists every change made since the approved proposal.

!tab Table A2.1: Feedback received and its resolution
!widths 1.8,0.9,1,2,0.6
| Issue | Source | Affected section | Action | Status |
| "Very hard to understand" | Sprint II review, 5 Nov 2026 | 2.6, 4.4 | The engine was rebuilt around plain files and five named steps, and the report describes it in standard terms | Done |
| "Just a report of benchmarks" | Sprint II review | 1.6, 5.4 | A usable app, a terminal chat and an MCP server were built around the engine; the scope now includes them | Done |
| Show it working with native Ollama models | Sprint II review | 5.2, 5.4 | Ollama is the only model runner; every local result was produced through it | Done |
| The person cannot create or remove their own collections | Sprint II review | 4.4 | The memory is the person's own folder of files; nothing is seeded | Done |
| Model activity should be visible | Sprint II review | 5.4.4 | The app states what the engine decided, the method used and the files read under each answer | Done |
| Can it generate reports natively? | Sprint II review | 5.4.5 | An answer can be kept as a note; no report format was built | Partly |
| If it codes, let it code, with live previews | Sprint II review | 1.6 | The app proposes changes to files for acceptance; live previews were not built | Partly |
| Keep each chapter to its own part, and follow the lecturer's guide for the structure of Chapters 1 to 6 and the references | Supervisor, November 2026 | Chapters 3 to 6 | Chapter 3 names the methods and points to Chapter 4; build detail moved to Chapter 5; side trials moved to Appendix 3; Chapter 6 added | Done |
| [PENDING: the written proposal comments and the proposal defence feedback, to be added by the student.] | Proposal defence, July 2026 | - | - | Open |

!include chapters4/changes-table.md

## Appendix 3: Further Results

The tables below support Section 5.5, and the two trials at the end of this appendix lie outside the specific objectives. Table A3.1 gives the small model, Table A3.2 the main model by subject, and Table A3.3 the paired tests. Table A3.4 and Table A3.5 give what the engine decided, Table A3.6 where the wrong answers came from, and Table A3.7 one question of each kind. Every answer is saved in the repository under trials/results/gap-1, and the full record of the 212 automated tests is in unit-tests-evaluation-2.log in the same folder.

!include generated2/accuracy-qwen3.5-4b.md

!include generated2/subjects.md

!include generated2/sign.md | Table A3.3 | 1.15,2.4,0.9,0.6,0.7,0.6

!include generated2/decisions.md

!include generated2/wrong.md | Table A3.6 | 1.15,1.8,0.8,1.3,1.3

!include generated2/examples.md | Table A3.7 | 1.1,2.9,2.3

Before the engine's five steps were built, retrieval alone was tested at tag evaluation-1. On 101 real bug fixes from four public repositories, following links reached a changed file on 72 and plain search on 59 (p = 0.002). On three held-back synthetic projects worked by simulated developer agents, memory did not measurably help the small model write working code. The simulated agents were programs, and no person took part. Those results are saved under trials/results and led to the engine described in this report.

### A Coding Trial Against the Cloud Model

A small trial asked whether the on-device model can build something beside the cloud model. Three briefs for a single-file website were given to Gemma 4 12B and to Claude: a matatu fare splitter, a clinic queue board that survives a reload, and a landing page with a phone menu and a pricing toggle. Each page was scored in a real browser with the same fixed checks, 42 in all. Figure A3.1 shows the pages.

!fig figures/v2/web-compare.png | Figure A3.1: The same three briefs built by Gemma 4 12B alone, by Gemma with a skill and a note of known failures, and by Claude alone | 6.2

Claude passed all 42 checks in every set-up. Gemma alone passed 41. With the brief the engine prepared, which carried a web-building skill, Gemma passed 39, because one page had a script error. With the skill and a note of known failures handed over directly, it passed 41, and that run had no such error. The engine had left the note out, because it judged each brief to be a task to work out. The trial is three briefs run once, so it is a demonstration and not a measurement.

### A Further Evaluation of Session Memory

A third evaluation, planned in advance like the second and run on a frozen binary, tested features added after the objectives were met. It used Qwen3 4B, a different model from the Qwen3.5 4B of Chapter 5, and its own 40 knowledge questions, half of the Evaluation 2 set split by a fixed seed, so its counts are not comparable with Table 5.5. None of the four features improved on its baseline. Table A3.8 shows that a pasted transcript carried a conversation further than the Ledger's handoff. Table A3.9 shows that notes Claude left on the other half of the questions added one answer to Burrow's 28 of 40. Table A3.10 shows that the line telling the model how much the vault holds did not change how often it declined, and Table A3.11 that four tools did no better than twelve. The plan, the frozen binary, every answer and the analysis are in the repository under trials/ledger and docs/report/evaluation-plan-3.md.

!include generated3/e1-resume.md | Table A3.8

!include generated3/e2-notes.md | Table A3.9

!include generated3/e3-trust.md | Table A3.10

!include generated3/e4-door.md | Table A3.11

## Appendix 4: Requirements Traceability

Table A4.1 traces each requirement to the part that implements it and the test that verifies it.

!tab Table A4.1: Traceability from requirement to component and test
!widths 1.05,0.8,2.1,1.2,1.15
| Requirement | Objective | Component | Test case | Result |
| FR-01 | iii | Vault, Scanner, Chunker | TC-01 | Pass |
| FR-02 | ii, iii | Retrieval, Index | TC-02 | Pass |
| FR-03 | ii, iii | Retrieval | TC-03 | Pass |
| FR-04 | ii | Engine.brief | TC-04, TC-05 | Pass |
| FR-05 | ii | Skills, Engine.brief | TC-06 | Pass |
| FR-06 | ii, v | Fit | TC-07 | Pass |
| FR-07 | iii | Engine.engage, Asking | TC-08 | Pass |
| FR-08 | ii | Engine.engage | TC-09 | Pass on the command line only |
| FR-09 | ii | Engine.lessons, keep | TC-10 | Pass in the terminal chat |
| FR-10 | iii | Engine.brief, BurrowMCP | TC-11 | Pass |
| NFR-01 | iii | Ollama | Inspection | Pass |
| NFR-02 | iii | Rebuildable index | TC-12 | Pass |
| NFR-03 | iii | Asking, ProjectContent | Automated tests | Pass on the tools path |
| NFR-04 | iv | Harness | Table 5.7 | Pass |
| NFR-05 | iii | Database | Inspection | Pass |
| NFR-06 | iii | Swift package | 212 automated tests | Pass on one machine |
| DR-01 | iii | Vault, linked folders | TC-18 | Pass |
| DR-02 | iii | Database, Index | TC-19 | Pass |
| DR-03 | ii | keep | TC-10 | Pass |
| DR-04 | iv | Harness | TC-20 | Pass |
| IR-01 | iii | Mac app | TC-08 | Pass |
| IR-02 | iii | Ollama, VaultTools | TC-21 | Pass |
| IR-03 | iii | BurrowMCP | TC-11 | Pass |
| IR-04 | iii | Vault | TC-22 | Pass |

## Appendix 5: User Guide

**What is needed.** A Mac with Ollama. Pull the models with ollama pull gemma4:12b and ollama pull qwen3-embedding:0.6b. Section 5.2.3 gives the one-command install from a tagged release; to build from source, run swift build -c release in the project folder and app/build.sh for the app.

**Using the app.**

i) Choose a folder as the vault. An existing Obsidian vault works as it is.
ii) Write notes in the centre pane and link notes with [[. A note's properties are shown as fields above its text, and holding Command over a link previews the note.
iii) To add code, choose Add, then Link a Folder.
iv) Open the graph to see how notes link, and search from the sidebar.
v) Open Programs to connect a model or tool, such as Claude Code, LM Studio or Ollama, through the MCP server. Its conversations then appear under Conversations, and what it understood appears in the Ledger.

**Using the terminal.**

i) burrow index <vault> --vault builds the index.
ii) burrow fit <vault> --model gemma4:12b measures the model once.
iii) burrow ask <vault> "question" --mode engine --model gemma4:12b answers through the engine.
iv) burrow chat <vault> opens a chat, and burrow tui <vault> the full-screen terminal view.
v) burrow resume <vault> prints where the last session stopped, for any model to carry on.

**Using Burrow from another model or tool.** burrow brief <vault> "task" --json returns the prepared prompt for any model. For an MCP client, run burrow mcp <vault>; by default it offers burrow_find, burrow_read, burrow_resume and burrow_commit. A client that is a cloud service sends what it reads to that service.

**Known limitations.** Burrow runs on macOS only. The check with retry runs only on burrow ask --mode engine; the app only warns, and the chat and MCP do not check.

## Appendix 6: More Screens of the System

Figure A6.1 shows a note in the reading view of the Mac app, and Figure A6.2 shows the terminal view of the same vault.

!fig figures/screens3/reading.png | Figure A6.1: A note in the reading view of the Mac app | 6.2

!fig figures/screens/terminal-star.png | Figure A6.2: The terminal view, with a note at the centre and its links around it | 6.2

## Appendix 7: AI-Use Log

Table A7.1 is the AI-use log. Full prompts and replies are retained in the Claude Code session transcripts on the development Mac. [PENDING: the student to add AI use before 9 November and to confirm this log.]

!tab Table A7.1: AI-use log
!widths 0.85,0.95,1.5,1.3,1.6
| Date (2026) | Tool and model | Used for | Retained output | Corrections and verification |
| 9 Nov | Claude Code | Plan and scope of Burrow, written with the student | Plan and DECISIONS.md | Reviewed and approved by the student |
| 9 Nov | Claude Code | Engine, command line, agent test harness | Source and tests | swift test |
| 9-10 Nov | Claude Code | Mac app, terminal view, chat and MCP server | Source and tests | swift test; screens reviewed by the student |
| 10 Nov | Claude Code | The earlier evaluation: held-back projects and real bug fixes | Code, projects, results | Plan written before scoring; results saved once |
| 10 Nov | Claude Code | The engine's five steps, skills and faster search, at the student's direction | Source, tests, DECISIONS.md D-50 to D-58 | 212 tests; thresholds set on development questions only |
| 10 Nov | Claude Code agents | Curated documents and questions; evaluation harness; vector database baseline | trials/gap | Checker scripts; fixture run; plan written before scoring |
| 10 Nov | Claude (claude-sonnet-5-5) through the API | The cloud model in the experiments | Saved answers | Scored by fixed answer keys |
| 10 Nov | Claude Code agents | Chapters 1 to 5 rewritten on the layout of earlier graduates' reports; a verified source pack; diagrams; tables and charts from saved results | Report and generators in docs/report | Each source confirmed at its published page; each change from the proposal listed in Table A2.2; tables generated by script |
| 10 Nov | Claude Code | The report laid out in Microsoft Word against the course guide; the conceptual framework redrawn; citations and the reference list placed as Mendeley Cite fields | Burrow_Report_Word.docx, guide-checklist.md | Every page of the exported PDF viewed; each section checked against the guide checklist |
| 11 Nov | Claude Code | The Ledger, hooks, terminal views, and a third evaluation of session memory with its plan written before scoring | Source, tests, trials/ledger, evaluation-plan-3.md | swift test; frozen binary; faults found in scoring reported, not fixed |
| 12 Nov | Claude Code | Recency and importance in the ranking; the report cut to each chapter's part; an independent review against the course guide; Chapter 6 and these appendices drafted | Source and tests; report text | 95 core tests; every figure in Chapter 6 traced to a section of Chapter 5; reviewed by the student |
| [PENDING: date] | - | The student's own review and edits of this report | - | - |

## Appendix 8: Similarity Report

[PENDING: the student to attach the one-page similarity report.]
