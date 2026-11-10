# Appendices 2 to 8, held out of the report on 10 Nov 2026 until the supervisor says what to add

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
| 10 | Documentation | [PENDING: date to be confirmed] | In progress |
| 11 | Project final defence | 23 November 2026 | Pending |

## Appendix 2: Feedback-Resolution Matrix

Table A2.1 records the feedback received and how each item was resolved. Table A2.2 lists every change made to Chapters 1 to 3 since the approved proposal.

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
| [PENDING: the written proposal comments and the defence feedback, to be added by the student.] | Proposal defence | - | - | Open |

!include chapters4/changes-table.md

## Appendix 3: Further Results

The tables below support Section 5.5. Table A3.1 gives the small model, Table A3.2 the main model by subject, and Table A3.3 the paired tests. Table A3.4 and Table A3.5 give what the engine decided, Table A3.6 where the wrong answers came from, and Table A3.7 one question of each kind. Every answer is saved in the repository under trials/results/gap-1, and the full record of the 212 automated tests is in unit-tests-evaluation-2.log in the same folder.

!include generated2/accuracy-qwen3.5-4b.md

!include generated2/subjects.md

!include generated2/sign.md | Table A3.3 | 1.15,2.4,0.9,0.6,0.7,0.6

!include generated2/decisions.md

!include generated2/wrong.md | Table A3.6 | 1.15,1.8,0.8,1.3,1.3

!include generated2/examples.md | Table A3.7 | 1.1,2.9,2.3

Before the engine's five steps were built, retrieval alone was tested at tag evaluation-1. On 101 real bug fixes from four public repositories, following links reached a changed file on 72 and plain search on 59 (p = 0.002). On three held-back synthetic projects worked by simulated developer agents, memory did not measurably help the small model write working code. The simulated agents were programs, and no person took part. Those results are saved under trials/results and led to the engine described in this report.

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

**What is needed.** A Mac with Xcode and Ollama. Pull the models with ollama pull gemma4:12b and ollama pull qwen3-embedding:0.6b.

**Building.** Run swift build -c release in the project folder for the command-line tool, and app/build.sh for the app. Open app/build/Burrow.app.

**Using the app.**

i) Choose a folder as the vault. An existing Obsidian vault works as it is.
ii) Write notes in the centre pane, and link notes with [[.
iii) To add code, choose Add, then Link a Folder.
iv) Open Ask and type a question. Under the answer the app shows what the engine decided, the method it used and the files it read.
v) To have a change proposed, use the change option beside the question field. Review it, then choose Accept or Reject.

**Using the terminal.**

i) burrow index <vault> --vault builds the index.
ii) burrow fit <vault> --vault --model gemma4:12b measures the model once.
iii) burrow skills <vault> --vault --install adds the starter skills to the vault's Skills folder. Edit them or add new ones as Markdown files with a when: line.
iv) burrow ask <vault> "question" --mode engine --model gemma4:12b --vault answers through the engine.
v) burrow chat <vault> opens a chat. /keep proposes notes from the conversation and asks before writing each one.

**Using Burrow from another model or tool.** burrow brief <vault> "task" --vault --json returns the prepared prompt for any model. For an MCP client, point it at the built program with the arguments mcp and the full path of the vault, and call vault_prepare. A client that is a cloud service sends what it reads to that service.

**Known limitations.** Burrow runs on macOS only. The check with retry runs only on burrow ask --mode engine; the app only warns, and the chat and MCP do not check. An empty question and a missing folder are not rejected.

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
| [PENDING: date] | - | The student's own review and edits of this report | - | - |

## Appendix 8: Similarity Report

[PENDING: the student to attach the one-page similarity report.]
