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

!include chapters2/changes-table.md

## Appendix 3: Requirements Traceability

Table A3.1 traces each requirement from its objective to the part that implements it, the diagram that designs it and the test that verifies it.

!tab Table A3.1: Traceability from objective to requirement, component, diagram and test
!widths 0.7,0.8,1.6,1.0,1.1,0.9
| Requirement | Objective | Component | Diagram | Test | Result |
| FR-01 | iii | `Vault`, `Scanner`, `Chunker` | 4.5, 4.9 | TC-01 | Pass |
| FR-02 | ii, iii | `Retrieval`, `Index` | 4.3, 4.7 | TC-02, TC-03 | Pass |
| FR-03 | ii, iii | `Retrieval` | 4.3 | TC-04 | Pass |
| FR-04 | ii | `Engine.brief` | 4.2, 4.6 | TC-05, TC-06 | Pass |
| FR-05 | ii | `Skills`, `Engine.brief` | 4.2, 4.6 | TC-07, TC-08 | Pass |
| FR-06 | ii, v | `Fit` | 4.6, 4.7 | TC-09, TC-10 | Pass |
| FR-07 | iii | `Engine.engage`, `Asking` | 4.3 | TC-11 | Pass |
| FR-08 | ii | `Engine.engage` | 4.3 | TC-12, TC-13 | Pass on the command line; not applied in the app or the chat (D-7) |
| FR-09 | ii | `Engine.lessons`, `keep` | 4.8, 4.11 | TC-14, TC-15 | Pass |
| FR-10 | iii | `Engine.brief`, `BurrowMCP` | 4.4 | TC-16 | Pass; the tool uses a fixed budget (D-8) |
| NFR-01 | iii | `Ollama` | 4.12 | Inspection | Pass |
| NFR-02 | iii | Rebuildable index | 4.9 | TC-17 | Pass |
| NFR-03 | iii | `Asking`, `ProjectContent` | 4.3 | TC-11, TC-18 | Pass on the tools path; open on the engine's own prompt (D-6) |
| NFR-04 | iv | `ChatResult`, harness | - | TC-19 | Pass |
| NFR-05 | iii | `Database` | 4.9, 4.12 | Inspection | Pass |
| NFR-06 | iii | Swift package | - | TC-20 | Pass on one machine |

!tab Table A3.2: Traceability from objective to result
!widths 2.3,1.5,2.4
| Objective | Evidence | Result |
| i. Investigate the gaps and existing techniques | Chapter 2 | Eight systems compared; the gap stated in Section 2.5 |
| ii. Design the engine | Chapter 4 | Five steps designed; recency and importance scoring not built |
| iii. Develop the engine | Chapter 5, Sections 5.2 to 5.4 | Built in Swift; 212 tests pass; three faults open |
| iv. Measure the gap closed by task type, with tokens and latency | Tables 5.9 to 5.14 | See Section 5.6.2 |
| v. Find the token budget that closes most gap per token | Table 5.17 | See Section 5.6.4 |

## Appendix 4: User Guide

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

## Appendix 5: Automated Test Record

Table A5.1 lists every automated test with its result on the frozen source. The full log is saved as `trials/results/gap-1/unit-tests-evaluation-2.log`.

!include generated2/tests.md

## Appendix 6: Every Question and Its Result

Table A6.1 lists every scored question with the result of each set-up on the main model and the cloud model. The answers themselves are saved in `trials/results/gap-1`.

!include generated2/questions.md

## Appendix 7: The Earlier Evaluation

Before the engine's five steps were built, retrieval alone was tested at tag `evaluation-1` on real bug fixes from four public repositories and on three held-back synthetic projects worked by simulated developer agents. Section 5.5.6 summarises those results. Table A7.1 lists the real bug-fix instances.

!include generated/real.md

## Appendix 8: AI-Use Log

Table A8.1 is the AI-use log. Full prompts and replies are retained in the Claude Code session transcripts on the development Mac. [PENDING: the student to add AI use before 9 November and to confirm this log.]

!tab Table A8.1: AI-use log
!widths 0.7,0.95,1.6,1.3,1.65
| Date (2026) | Tool and model | Used for | Retained output | Corrections and verification |
| 9 Nov | Claude Code | Plan and scope of Burrow, written with the student | Plan and `DECISIONS.md` | Reviewed and approved by the student |
| 9 Nov | Claude Code | Engine, command line, agent test harness | Source and tests | `swift test` |
| 9-10 Nov | Claude Code | Mac app, terminal view, chat and MCP server | Source and tests | `swift test`; screens reviewed by the student |
| 10 Nov | Claude Code | The earlier evaluation: held-back projects and real bug fixes | Code, projects, results | Plan written before scoring; results saved once |
| 10 Nov | Claude Code | The engine's five steps, skills and faster search, at the student's direction | Source, tests, `DECISIONS.md` D-50 to D-58 | 212 tests; thresholds set on development questions only |
| 10 Nov | Claude Code agents | Curated documents and questions; evaluation harness; vector database baseline | `trials/gap` | Checker scripts; fixture run; plan written before scoring |
| 10 Nov | Claude (`claude-sonnet-5-5`) through the API | The cloud model in the experiments | Saved answers | Scored by fixed answer keys |
| 10 Nov | Claude Code agents | Revision of Chapters 1 to 4 from the approved proposal; diagrams; this chapter's tables from saved results | Report and generators in `docs/report` | Each change from the proposal listed in Table A2.2; tables generated by script |
| [PENDING] | - | The student's own review and edits of this report | - | - |

## Appendix 9: Similarity Report

[PENDING: attach the one-page similarity report.]
