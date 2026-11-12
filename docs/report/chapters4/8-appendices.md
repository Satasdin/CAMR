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
| 5 | Chapters 1 to 3 submitted | 12 June 2026 | Done |
| 6 | Semester I oral defence | 13 to 16 July 2026 | Done |
| 7 | Marking and revision of Chapters 1 to 3 | 31 July 2026 | Done |
| 8 | Chapter 4: System Analysis and Design | 17 August 2026 | Done |
| 9 | Sprint II review | 5 November 2026 | Done |
| 10 | Documentation | November 2026 | In progress |
| 11 | Project final defence | 23 November 2026 | Pending |

## Appendix 2: Feedback-Resolution Matrix

Table A2.1 records the feedback received and how each item was resolved.

!tab Table A2.1: Feedback received and its resolution
!widths 1.8,0.9,1,2,0.6
| Issue | Source | Affected section | Action | Status |
| "Very hard to understand" | Sprint II review, 5 Nov 2026 | 2.6, 4.4 | The engine was rebuilt around plain files and five named steps, and the report describes it in standard terms | Done |
| "Just a report of benchmarks" | Sprint II review | 1.6, 5.4 | A usable app, a terminal chat and an MCP server were built around the engine; the scope now includes them | Done |
| Show it working with native Ollama models | Sprint II review | 5.2, 5.4 | Ollama is the only model runner; every local result was produced through it | Done |
| The person cannot create or remove their own collections | Sprint II review | 4.4 | The memory is the person's own folder of files; nothing is seeded | Done |
| Model activity should be visible | Sprint II review | 5.4.4 | The app shows every program that uses the vault, each conversation's lookups and the files read; the command line states what the engine decided | Done |
| Can it generate reports natively? | Sprint II review | 5.4.5 | A conversation, or a decision from it, can be kept in the Ledger and handed to the next model; no report format was built | Partly |
| If it codes, let it code, with live previews | Sprint II review | 1.6 | Coding is left to the programs that connect to the vault, such as OpenCode and Claude Code, which read the code and its decisions through Burrow; live previews were not built | Partly |
| Keep each chapter to its own part, and follow the lecturer's guide for the structure of Chapters 1 to 6 and the references | Supervisor, November 2026 | Chapters 3 to 6 | Chapter 3 names the methods and points to Chapter 4; build detail moved to Chapter 5; side trials moved to the repository's further results; Chapter 6 added | Done |
| Abstract scored 2 of 3 (at most 200 words) | Written assessment, Ms. Eunice Manyasi, 30 June 2026 (37 of 40; "The document is well written") | Abstract | Rewritten last, from the final results, within 200 words | Done |
| Problem statement scored 3 of 4 (background, clarity, gap, citations) | Written assessment, 30 June 2026 | 1.2 | The ideal, the reality and the gap stated with cited evidence, and the consequence quantified | Done |
| Objectives scored 3 of 4 (SMART and linked to the problem) | Written assessment, 30 June 2026 | 1.3, 6.2 | Each objective now has a measured result and a verdict in Section 5.9 and Chapter 6 | Done |
| The appendices and Chapter 5 are too long; some of it belongs on GitHub; show how the system works with a model | Review of the draft, 12 November 2026 | Chapter 5, appendices | The full test record, further results and extra screens moved to the repository and linked; Section 5.4.7 shows the workflows with a model from real runs | Done |
| [PENDING: the oral defence feedback from Semester I, to be added by the student.] | Oral defence, July 2026 | - | - | Open |

## Appendix 3: Requirements Traceability

Table A3.1 traces each requirement to the part that implements it and the test that verifies it.

!tab Table A3.1: Traceability from requirement to component and test
!widths 1.05,0.8,2.1,1.2,1.15
| Requirement | Objective | Component | Test case | Result |
| FR-01 | iii | Vault, Scanner, Chunker | TC-01 | Pass |
| FR-02 | ii, iii | Retrieval, Index | TC-02 | Pass |
| FR-03 | ii, iii | Retrieval | TC-03 | Pass |
| FR-04 | ii | Engine.brief | TC-04, TC-05 | Pass |
| FR-05 | ii | Skills, Engine.brief | TC-06 | Pass |
| FR-06 | ii, v | Fit | TC-07 | Pass |
| FR-07 | iii | Engine.engage | TC-08 | Pass |
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
| IR-01 | iii | Mac app, conversation page | TC-08 | Pass |
| IR-02 | iii | Ollama, VaultTools | TC-21 | Pass |
| IR-03 | iii | BurrowMCP | TC-11 | Pass |
| IR-04 | iii | Vault | TC-22 | Pass |

## Appendix 4: User Guide

**What is needed.** A Mac with Ollama. Pull the models with ollama pull gemma4:12b and ollama pull qwen3-embedding:0.6b. Section 5.2.3 gives the one-command install from a tagged release; to build from source, run swift build -c release in the project folder and app/build.sh for the app.

**Using the app.**

i) Choose a folder as the vault. An existing Obsidian vault works as it is.
ii) Write notes in the centre pane and link notes with [[. A note's properties are shown as fields above its text, and holding Command over a link previews the note.
iii) To add code, choose Add, then Link a Folder.
iv) Open the graph to see how notes link, and search from the sidebar.
v) Open Programs to connect a model or tool, such as Claude Code, LM Studio or Ollama, through the MCP server: press Connect, then Copy, or Add for Me to write the setting into the program. Its conversations then appear under Conversations as it works, and what it understood appears in the Ledger.

**Using the terminal.**

i) burrow index <vault> --vault builds the index.
ii) burrow fit <vault> --model gemma4:12b measures the model once.
iii) burrow ask <vault> "question" --mode engine --model gemma4:12b answers through the engine.
iv) burrow chat <vault> opens a chat, and burrow tui <vault> the full-screen terminal view.
v) burrow resume <vault> prints where the last session stopped, for any model to carry on.

**Using Burrow from another model or tool.** burrow brief <vault> "task" --json returns the prepared prompt for any model. For an MCP client, run burrow mcp <vault>; by default it offers burrow_find, burrow_read, burrow_resume and burrow_commit. A client that is a cloud service sends what it reads to that service.

**Known limitations.** Burrow runs on macOS only. The check with retry runs only on burrow ask --mode engine; the chat and MCP do not check. The app does not ask questions itself; the program connected to the vault does.

## Appendix 5: AI-Use Log

Table A5.1 is the AI-use log. Full prompts and replies are retained in the Claude Code session transcripts on the development Mac. [PENDING: the student to add AI use before 9 November and to confirm this log.]

!tab Table A5.1: AI-use log
!widths 0.85,0.95,1.5,1.3,1.6
| Date (2026) | Tool and model | Used for | Retained output | Corrections and verification |
| 9 Nov | Claude Code | Plan and scope of Burrow, written with the student | Plan and DECISIONS.md | Reviewed and approved by the student |
| 9 Nov | Claude Code | Engine, command line, agent test harness | Source and tests | swift test |
| 9-10 Nov | Claude Code | Mac app, terminal view, chat and MCP server | Source and tests | swift test; screens reviewed by the student |
| 10 Nov | Claude Code | The earlier evaluation: held-back projects and real bug fixes | Code, projects, results | Plan written before scoring; results saved once |
| 10 Nov | Claude Code | The engine's five steps, skills and faster search, at the student's direction | Source, tests, DECISIONS.md D-50 to D-58 | 212 tests; thresholds set on development questions only |
| 10 Nov | Claude Code agents | Curated documents and questions; evaluation harness; vector database baseline | trials/gap | Checker scripts; fixture run; plan written before scoring |
| 10 Nov | Claude (claude-sonnet-5-5) through the API | The cloud model in the experiments | Saved answers | Scored by fixed answer keys |
| 10 Nov | Claude Code agents | Chapters 1 to 5 rewritten on the layout of earlier graduates' reports; a verified source pack; diagrams; tables and charts from saved results | Report and generators in docs/report | Each source confirmed at its published page; each change recorded with its reason in Section 5.4.8; tables generated by script |
| 10 Nov | Claude Code | The report laid out in Microsoft Word against the course guide; the conceptual framework redrawn; citations and the reference list placed as Mendeley Cite fields | Burrow_Report_Word.docx, guide-checklist.md | Every page of the exported PDF viewed; each section checked against the guide checklist |
| 11 Nov | Claude Code | The Ledger, hooks, terminal views, and a third evaluation of session memory with its plan written before scoring | Source, tests, trials/ledger, evaluation-plan-3.md | swift test; frozen binary; faults found in scoring reported, not fixed |
| 12 Nov | Claude Code | Recency and importance in the ranking; the report cut to each chapter's part; an independent review against the course guide; Chapter 6 and these appendices drafted | Source and tests; report text | 95 core tests; every figure in Chapter 6 traced to a section of Chapter 5; reviewed by the student |
| 12 Nov | Claude Code | The flow of the report checked against the course guide; the built application benchmarked against what was planned for it; the Programs page redrawn with live activity; the final title, tenses and wording | Report text; app source; guide-checklist.md | Test build of the report; every changed screen captured from a real run |
| 12 Nov | Claude Code | GitHub: a test workflow that runs every automated test on each push, a compiler fix it found, and the final release | .github/workflows/tests.yml; release on GitHub | The workflow's own run; tests passed locally and on GitHub |
| 12 Nov | Claude Code | Demonstration clips recorded from the real application, terminal and models, for the student to edit | docs/demo/clips | Each clip from a real run on the evaluation vault; nothing staged |
| [PENDING: date] | - | The student's own review and edits of this report | - | - |

## Appendix 6: Similarity Report

[PENDING: the student to attach the one-page similarity report.]
