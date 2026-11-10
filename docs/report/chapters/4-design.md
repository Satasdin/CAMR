# Chapter 4:  System Analysis and Design

## 4.1 Introduction

This chapter explains what Burrow must do, the quality conditions it must satisfy, the data and interfaces it depends on, and the diagrams that communicate its structure and behaviour. The development paradigm justified in Chapter 3 is Object-Oriented Analysis and Design, so the chapter uses Unified Modeling Language (UML) views.

Section 4.2 presents the system requirements. Section 4.3 presents the analysis diagrams: the use case diagram with its descriptions, activity diagrams, sequence diagrams and an analysis class diagram. Section 4.4 presents the design diagrams: the system architecture, the retrieval design, a design class diagram, a state machine diagram, the logical database schema, interface wireframes and a deployment diagram. The selection follows the views normally used with OOAD.

## 4.2 System Requirements

The system requirements identified for this project are presented in the following subsections. Following the requirements-engineering guidance of ISO/IEC/IEEE 29148:2018 (International Organization for Standardization et al., 2018), each requirement has a unique identifier, a priority, a source or rationale and a method of verification. Priority is given as Must, meaning that the objectives cannot be met without it, or Should, meaning that it improves the product but that the objectives could be met without it. The stakeholders are the person who owns the vault and, in the evaluation, the examiner who needs to verify the claims. Appendix 3 traces each requirement back to an objective and forward to a feature, diagram and test.

### 4.2.1 Functional Requirements

Table 4.1 is the catalogue of functional requirements.

!tab Table 4.1: Functional requirements catalogue
!widths 0.65,3.2,0.6,1.3,0.75
| ID | Requirement | Priority | Source or rationale | Verification |
| FR-01 | The system shall open any folder as a vault, and shall treat every Markdown file in it as a note, so that an existing Obsidian vault works unchanged. | Must | A person owns their notes (Section 2.4) | Test |
| FR-02 | The system shall allow a person to create, edit, rename, move and delete notes and folders. | Must | Sprint II feedback: people need their own collections | Test |
| FR-03 | The system shall allow a code folder to be linked into a vault under its own name, and shall leave its files unchanged unless a person accepts a proposed change. | Must | Code must not be altered without consent | Test |
| FR-04 | The system shall bring its index up to date by re-reading only the files that have changed. | Must | A vault changes between sessions | Test |
| FR-05 | The system shall connect files through wiki links, Markdown links, code imports, uses of defined names, and notes that name code. | Must | Link walking needs links that can be checked (D-4) | Test |
| FR-06 | The system shall find text by exact words and by meaning, and shall show the matching line. | Must | Exact names and meaning are both needed (D-3) | Test |
| FR-07 | The system shall answer a question through a local Ollama model using retrieved excerpts, and shall name the files and lines used. | Must | Answers must be checkable | Test |
| FR-08 | The system shall allow a question to be limited to one folder, and shall read nothing outside it. | Must | Defect DEF-03 and D-41 | Test |
| FR-09 | The system shall support three retrieval modes, none, search and walk, each held to the same character limit. | Must | Required by the experimental design (D-7) | Test |
| FR-10 | The system shall write a model's proposed change to a file only when a person accepts it and the file has not changed since the proposal. | Must | Human oversight (D-26) | Test |
| FR-11 | The system shall allow an answer to be kept as a note, and shall never overwrite an existing note when doing so. | Should | Knowledge should build up | Test |
| FR-12 | The system shall show the vault as an interactive graph of files and links, and shall mark the files used for an answer. | Should | Sprint II feedback: model activity should be visible | Demonstration |
| FR-13 | The system shall provide a full-screen terminal view for reading the vault and asking questions. | Should | Developers work in terminals | Test |
| FR-14 | The system shall provide a terminal chat that lets a local model call the vault's tools. | Should | `ollama run` has no tool support in version 0.40.14 (D-32) | Test |
| FR-15 | The system shall provide a Model Context Protocol (MCP) server with seven tools: search, read, links, list, folders, remember and ask. | Should | Other assistants can use the vault | Test |

Table 4.2 describes the system's modules by actor, trigger, expected behaviour, output and important exceptions.

!tab Table 4.2: Functional modules
!widths 0.9,0.7,0.9,1.7,1.0,1.3
| Module | Actor | Trigger | Expected behaviour | Output | Important exceptions |
| Vault and notes | Person | Opens a folder; creates or edits a note | Reads every Markdown file as a note; saves plain files | Files on disk, updated list | A path outside the vault is refused |
| Linked folders | Person | Chooses a folder to link | Adds it under a name; indexes it without changing it | Folder shown in the file tree | A folder in iCloud must be downloaded before it can be indexed |
| Index | System | Vault opened; files changed | Re-reads only changed files, rebuilds links, adds vectors | Up-to-date index | Ollama unreachable: indexing continues on words alone |
| Search | Person | Types a search | Ranks pieces by words and meaning | Matching lines | Search characters in the text are treated as words |
| Ask | Person, Ollama | Submits a question | Retrieves excerpts within the limit, then generates | Answer with files and lines | Model unreachable: the failure is stated; nothing recorded: the model is told to say so |
| Proposed change | Person, Ollama | Asks for a change | Shows old and new text; writes on acceptance | Changed file, or no change | File changed since the proposal: nothing is written |
| Tools | MCP client, local model | Tool call | Reads the indexed vault; only remember writes | Tool result with excerpts | A call that does not fit the definition is an error; a tool that cannot complete returns a readable failure |

### 4.2.2 Non-Functional Requirements

The quality areas selected from the product-quality model of ISO/IEC 25010:2023 (International Organization for Standardization & International Electrotechnical Commission, 2023) are those relevant to a private tool on one device: confidentiality and integrity, reliability, compatibility and maintainability. Table 4.3 gives the requirements. No response-time threshold was set in advance, because no stakeholder need or user research existed to justify one, and an invented threshold would have given a false appearance of measurement. NFR-09 therefore requires that speed be measured under a stated workload, and the observed values are reported in Section 5.7.

!tab Table 4.3: Non-functional requirements catalogue
!widths 0.7,3.3,0.6,1.2,0.75
| ID | Requirement | Priority | Source or rationale | Verification |
| NFR-01 | When answering or indexing, Burrow shall send notes and code only to the local Ollama address, 127.0.0.1. | Must | Privacy is the reason for the project | Inspection |
| NFR-02 | Deleting the index shall lose no note or code, and the next refresh shall restore it. | Must | The files are the truth (D-2) | Test |
| NFR-03 | Text from files shall be presented to a model as data, and shall be unable to end its marked block early. | Must | Indirect prompt injection (Section 2.3) | Test |
| NFR-04 | Tools shall be unable to open a path outside the vault, a git-ignored file, or Burrow's own store. | Must | Confidentiality | Test |
| NFR-05 | Under a rebuild of 300 files with 8 concurrent question tasks, repeated for 4 rounds, the index shall not corrupt, as shown by the SQLite integrity check. | Must | Defect DEF-06 | Test |
| NFR-06 | Text from a file shall be unable to send control sequences to the terminal. | Must | A note must not control the terminal (D-35) | Test |
| NFR-07 | A second person shall be able to build and run Burrow from the README alone. | Must | Handover: another person must be able to run the system | Demonstration |
| NFR-08 | No retrieval mode shall supply more than 12,000 characters of excerpts for one question. | Must | Fair comparison (D-7) | Test |
| NFR-09 | For each test repository, first index time, index size, and median and longest retrieval time shall be measured and reported. | Should | Growth objective, v(d) | Measurement |
| NFR-10 | The terminal view shall stay readable with colour disabled, and shall say so when the window is below 40 by 12 characters. | Should | Accessibility of meaning (D-34) | Test |
| NFR-11 | The whole test suite shall run with one command and shall exit with code 0 before any commit. | Must | Maintainability and testability | Inspection |

### 4.2.3 Data Requirements

Burrow's inputs are Markdown notes and source files that belong to the person. Its outputs are answers, proposed changes, kept notes and a derived index. Validation consists of the extension and size rules in Section 3.2.2, and duplicates are controlled by a unique path per file and a digest of its content. Table 4.4 gives the requirements. Evaluation data requirements are included because the claims in Chapter 5 depend on them.

!tab Table 4.4: Data requirements catalogue
!widths 0.65,3.3,0.6,1.3,0.75
| ID | Requirement | Priority | Source or rationale | Verification |
| DR-01 | Notes shall be ordinary Markdown files that can be read without Burrow. | Must | Ownership and longevity (Section 2.4) | Test |
| DR-02 | An index built by an older version shall rebuild itself. | Must | Upgrades must not leave stale data | Test |
| DR-03 | Every line of an indexed file shall land in exactly one piece, and no piece shall exceed 80 lines or 3,000 characters. | Must | Defect DEF-05 | Test |
| DR-04 | Hidden, ignored and dependency folders shall be left out of the index, as shall large data files. | Must | Privacy and retrieval quality (D-9) | Test |
| DR-05 | The index shall be held on the device in the vault's `.burrow` folder and shall contain only what can be rebuilt from the files. | Must | Retention and deletion: removing the folder removes the derived data | Test |
| DR-06 | Tuning material and held-back material shall be kept apart, and held-back projects shall be marked `split: held` and scored once. | Must | Prevents test-set tuning | Inspection |
| DR-07 | A results folder shall be written once, and a run shall refuse to overwrite an existing one. | Must | Audit and reproducibility (D-23) | Inspection |

### 4.2.4 Interface and Integration Requirements

Table 4.5 gives the interface and integration requirements, including what happens when an integration is unavailable.

!tab Table 4.5: Interface and integration requirements catalogue
!widths 0.65,3.3,0.6,1.3,0.75
| ID | Requirement | Priority | Source or rationale | Verification |
| IR-01 | The engine shall reach models only through Ollama's HTTP interface at 127.0.0.1, port 11434. | Must | One local runtime | Inspection |
| IR-02 | The MCP server shall use line-delimited JSON-RPC 2.0 over standard input and output. | Should | Protocol specification | Test |
| IR-03 | If Ollama cannot be reached, search shall continue on words alone and a question shall report the failure and not an empty answer. | Must | Graceful failure | Test |
| IR-04 | A tool call that does not match its definition shall return JSON-RPC error -32602, and a tool that cannot do its job shall return a readable result with `isError` set. | Should | D-31 | Test |
| IR-05 | The Mac app shall follow macOS conventions: a sidebar, tabs, an inspector and standard windows, on macOS 26 or later. | Should | Sprint II feedback and platform choice | Demonstration |
| IR-06 | The terminal view shall work in a UTF-8 terminal of at least 40 by 12 characters and shall respect `NO_COLOR`. | Should | Terminal users | Test |

## 4.3 System Analysis Diagrams

This section presents the diagrams used to analyse the actors, processes and concepts of the system. Each is preceded by its purpose and followed by an interpretation. The drawings are generated from `docs/report/figures/diagrams.py`, which is retained as their editable source.

### 4.3.1 Use Case Diagram

Figure 4.1 shows how external actors interact with Burrow and which services it exposes. It is relevant because it fixes the system boundary and shows who may do what. It addresses FR-01 to FR-12 and FR-15 and objective iv.

!fig figures/use_cases.png | Figure 4.1: Use case diagram of Burrow. | 5.9

A person is the primary actor. Ollama and an MCP client are external programs that interact with the system, and they are the only non-human actors, since databases and internal modules are not actors. Asking a question always includes retrieving excerpts and generating the answer, which is why those two use cases are linked by «include»: a question cannot be answered without them. Limiting the question to a folder, proposing a change and keeping the answer are optional behaviour and are therefore «extend» relationships, which keeps a plain question to one step.

Accepting or rejecting a proposed change is a separate use case belonging only to the person, because nothing may be written until a person decides. The MCP client has access only to the tools and has no route to the editor or to accepting changes, and this limits what a connected assistant can do.

### 4.3.2 Use Case Descriptions

Tables 4.6 to 4.9 describe the four use cases that carry the main risk, using the names in Figure 4.1. A local model using the terminal chat calls the same tools as an MCP client, and is shown in Table 4.9 for that reason.

!tab Table 4.6: Use case description: Ask a question
!widths 1.5,4.7
| Item | Description |
| Actors | Person (primary), Ollama (supporting) |
| Requirements | FR-06, FR-07, FR-08, FR-09 |
| Precondition | A vault is open and Ollama is running with a chat model |
| Main flow | 1. The person types a question and may choose a folder. 2. Burrow retrieves excerpts within the limit. 3. The sources are shown. 4. The model reads the marked excerpts and generates. 5. The answer appears with its files and lines. |
| Alternative flows | The person limits the question to a folder, so that nothing outside it is read. The person keeps the answer as a note. |
| Exceptions | Ollama cannot be reached, so the failure is reported. Nothing relevant is found, so the model is told to say it does not know. |
| Postcondition | No file has changed unless the person later keeps a note or accepts a change |

!tab Table 4.7: Use case description: Link a code folder
!widths 1.5,4.7
| Item | Description |
| Actors | Person |
| Requirements | FR-03, FR-04, FR-05 |
| Precondition | A vault is open |
| Main flow | 1. The person chooses a folder. 2. Burrow records the link under the folder's name. 3. The folder's text files are indexed and its links are extracted. 4. The folder appears in the file tree, marked as linked. |
| Exceptions | Files held only in iCloud have to be downloaded first, and the index waits for them. |
| Postcondition | The folder can be read and searched; its files are read-only unless a proposed change is accepted |

!tab Table 4.8: Use case description: Accept or reject a proposed change
!widths 1.5,4.7
| Item | Description |
| Actors | Person |
| Requirements | FR-10 |
| Precondition | The model has proposed a change, shown as a line-by-line comparison |
| Main flow | 1. The person reviews the comparison. 2. The person accepts. 3. Burrow reads the file and confirms that it still matches the text the proposal was based on. 4. The new text is written. |
| Alternative flows | The person rejects the change, and the file is left alone. |
| Exceptions | The file has changed since the proposal, so nothing is written and this is reported. The path lies outside the vault, so the change is refused. |
| Postcondition | The file holds the new text only if the person accepted and the file was unchanged |

!tab Table 4.9: Use case description: Call vault tools
!widths 1.5,4.7
| Item | Description |
| Actors | MCP client, or a local model through the terminal chat |
| Requirements | FR-14, FR-15, NFR-03, NFR-04 |
| Precondition | The server has been started on a vault |
| Main flow | 1. The client initialises and lists the seven tools. 2. It calls a tool with arguments. 3. Burrow runs the tool against the indexed vault. 4. It returns the result, with project text marked as data. |
| Exceptions | Invalid arguments return a protocol error. A path that is not indexed is refused. In the terminal chat, a model cannot keep a note unless the person agrees. |
| Postcondition | Only `vault_remember` writes, and it only adds a note |

### 4.3.3 Activity Diagrams

Two activities carry the system's main logic. Figure 4.2 shows how the index is brought up to date, which addresses FR-04, FR-05, DR-02 and DR-04. It is relevant because the index must stay correct without rereading every file for every change.

!fig figures/activity_index.png | Figure 4.2: Activity diagram of refreshing the index. | 5.2

A digest of each file decides whether it is processed, so an unchanged file costs one read and no further work. Links, in contrast, are rebuilt in full on every refresh, because one changed file can alter what a name in another file refers to. Vectors are the only step that depends on Ollama, and the decision node shows that the index remains usable without them. Separately, the tools compare a short summary of the file tree before calling this activity, so that a tool call costs no file reads when nothing has changed (D-39).

Figure 4.3 follows one question across the person, the engine and the model. It is the main path behind FR-06 to FR-09.

!fig figures/activity.png | Figure 4.3: Activity diagram of answering a question. | 5.7

All selection happens in the engine before the model is called. The model reads the result and plays no part in choosing what is read, which keeps retrieval checkable and repeatable (D-6). If Ollama cannot be reached, retrieval continues on words alone.

### 4.3.4 Sequence Diagrams

Sequence diagrams show the order of messages between objects over time. Figure 4.4 shows a question asked in the Mac app and addresses FR-06 and FR-07.

!fig figures/sequence.png | Figure 4.4: Sequence diagram of a question asked in the Mac app. | 6.0

Sources appear on screen before the answer begins, so a person can see what the model was given before it says anything. The workspace object stays active for the whole exchange and streams words as they arrive, while the vault is active only during retrieval.

Figure 4.5 shows a proposed change, which is the design behind FR-10 and the human oversight described in Section 3.2.4.

!fig figures/sequence_change.png | Figure 4.5: Sequence diagram of proposing and accepting a change. | 6.0

The model's reply stops at the proposal: the model has no path to the file system. The write happens only after the person's message, and it is guarded by a comparison made at the moment of writing. A person who edits the file while reading the proposal is therefore protected from having that edit overwritten.

### 4.3.5 Analysis Class Diagram

Figure 4.6 models the concepts of the problem domain before any implementation decision. It establishes the vocabulary used across all the diagrams and addresses objective iv.

!fig figures/domain.png | Figure 4.6: Analysis class diagram of the problem domain. | 6.0

A vault holds files, and a linked folder contributes files without being moved. A link connects two files and records the kind of relationship and the name that made it, which is what allows a walk to be explained afterwards. A file is cut into pieces, and an answer cites pieces rather than whole files, which is why answers can name lines. A proposed change belongs to an answer and records the text it was based on, and that record is what makes the guard in Figure 4.5 possible.

## 4.4 System Design Diagrams

This section describes how the solution was organised to satisfy the analysed requirements.

### 4.4.1 System Architecture

Figure 4.7 shows the components and their main dependencies. It addresses the need for every interface to behave identically and supports the claim that the tests measure what ships.

!fig figures/architecture.png | Figure 4.7: Component diagram of Burrow, showing the main dependencies. | 6.2

`BurrowCore` holds everything to do with files, the index and retrieval, and every interface depends on it. `BurrowTools` defines the seven tools once, so that a tool cannot behave one way for the terminal chat and another way for an MCP client (D-27). The Mac app reuses the reply format from the agent test, so that a proposed change in the app follows the format that was tested (D-26). The only component that speaks to the model runtime is the Ollama client, which keeps the privacy requirement NFR-01 easy to inspect.

### 4.4.2 Retrieval Design

Retrieval takes place in four steps and addresses FR-06 and FR-09. First, a question is ranked twice: by word search with BM25 over the paths and text of pieces (Robertson & Zaragoza, 2009), and by cosine similarity between its vector and each stored vector, as in Equation 4.1, where q is the vector of the question and v that of a piece.

!eq cosine | Equation 4.1: Cosine similarity between a question and a piece.

The two rankings are merged with reciprocal rank fusion (Cormack et al., 2009), as in Equation 4.2, where the rank of piece p in each ranking r counts from 1, and w(p) is the weight described below. Bruch et al. (2023) found that a tuned convex combination of scores can do better, but that method requires labelled examples, which do not exist for a person's own vault, so a method that uses ranks alone was selected.

!eq rrf | Equation 4.2: Merged score of a piece.

Second, the merged score is adjusted. Tests take a weight of 0.7 and the output of past runs a weight of 0.4, unless the question asks for them or names them, because these files repeat the words of the code they concern (D-45). Everything else, and all Markdown notes, take a weight of 1. Pieces holding a compound name typed in the question, or belonging to a file or folder the question names, are placed first (D-12).

Third, in walk mode the best piece of up to four files is taken as an entry point, using at most 60% of the character limit. Burrow then follows links for up to two hops. A neighbouring file n is ranked by Equation 4.3, where b(n) is its word match scaled so that the best file scores 1, h is the hop number, and k(n) depends on the kind of link: 3 if a note is about the file, 1 if it is imported, or 0.5 in the reverse direction, and 0.75 if a name in it is used, or 0.25 in the reverse direction.

!eq walk | Equation 4.3: Score of a neighbouring file during a walk.

Fourth, if the links run out before the limit, the remainder is spent on further search results (D-7). The two modes differ in how they use the limit. Walk carries on past a piece that does not fit and takes one piece from each entry file, while search stops at the first piece that would exceed the limit and can take several pieces from one file. Walk's first file is by construction the same as search's first file. Both points matter for interpreting the results in Chapter 5.

### 4.4.3 Design Class Diagram

Figure 4.8 shows the main types of the engine as they were implemented and refines the analysis classes of Figure 4.6.

!fig figures/classes.png | Figure 4.8: Design class diagram of the main engine types. | 6.0

`Vault` is the entry point and owns one `Database`. Chunking, scanning and link finding are stateless utilities, which makes them simple to test on their own. `Budget` holds the limits in one place, so a limit cannot differ between modes. Each `Excerpt` carries a `Reason`, so that the interface can state why any piece of text was read. The `Embedder` and `Answerer` protocols allow tests to run without a real model.

### 4.4.4 State Machine Diagram

Figure 4.9 shows the states of a proposed change and supports FR-10.

!fig figures/states.png | Figure 4.9: State machine diagram of a proposed change. | 6.1

A change has one path to the file, and that path passes through a guard. Both Accepted and Rejected are final. If the guard fails, the change stays waiting and the problem is reported, so a person can read the current file and ask again.

### 4.4.5 Logical Database Schema

Figure 4.10 shows the logical schema of the index, held in one SQLite file. It addresses FR-04 to FR-06, NFR-02 and DR-05.

!fig figures/schema.png | Figure 4.10: Logical schema of the index. | 6.1

A file has many pieces, stored as `chunks`, and a piece has at most one vector, because embedding is optional. `chunks_fts` is a full-text table that shares its row identifiers with `chunks`. The schema is normalised so that the file path is stored once in `files` and pieces refer to it by foreign key; `chunks_fts` deliberately repeats the path, because searching over the path is part of ranking. `links` refers to files by path and not by foreign key, because all links are deleted and rebuilt together on every refresh, so a stale reference cannot survive. Deleting a file cascades to its pieces and their vectors, which preserves integrity without application code. The entire database can be rebuilt from the files (D-2).

### 4.4.6 User Interface Wireframes

The wireframes below show the arrangement of each screen and address FR-02, FR-07, FR-10, FR-12, FR-13 and IR-05. They show layout and content regions only. Captures of the finished interface appear in Section 5.3.1. Figure 4.11 shows how a person moves between screens, and it is relevant because it establishes what can be reached from where.

!fig figures/screen_flow.png | Figure 4.11: Screen flow of the Mac app. | 6.0

A person reaches every page from one window, and asking a question does not require leaving it. Review of a change and keeping a note are both reached only from an answer, so they cannot occur without something to review.

Figure 4.12 shows the main window with a note open. It represents the screen on which most time is spent and addresses FR-01, FR-02 and IR-05.

!fig figures/wire_main.png | Figure 4.12: Wireframe of the main window with a note open. | 6.0

The window follows the macOS arrangement of sidebar, content and inspector. The note occupies the centre, and the inspector places the note's relationships beside it, so that links can be followed without leaving the text.

Figure 4.13 shows the Ask page, and it addresses FR-07, FR-08 and FR-10. The page is relevant because a person must be able to judge an answer against its sources before relying on it.

!fig figures/wire_ask.png | Figure 4.13: Wireframe of the Ask page. | 6.0

The reading strip lies above the answer, because sources appear before generation begins. Accept and Reject are placed beside the proposed change and carry equal weight, so that review remains an explicit act. The folder limit sits beside the question field, because it changes what the question means.

Figure 4.14 shows the graph page. It addresses FR-12, and its scope is the whole vault as files and links.

!fig figures/wire_graph.png | Figure 4.14: Wireframe of the graph page. | 6.0

The graph fills the content area and a question can be asked from it directly, so that the files read for the answer are seen where they are. The filter panel is placed over a corner because a person only needs it occasionally.

Figure 4.15 shows the terminal view at its widest. It addresses FR-13 and IR-06 and is relevant because the same vault must remain usable without the app.

!fig figures/wire_terminal.png | Figure 4.15: Wireframe of the terminal view at full width. | 6.0

The terminal view drops the side pane in middle-sized windows, and shows only the focused pane in narrow ones, so that reading text remains the priority at any size.

### 4.4.7 Deployment Diagram

Figure 4.16 shows where each part runs and addresses NFR-01 and IR-01.

!fig figures/deployment.png | Figure 4.16: Deployment diagram of Burrow on one Mac. | 6.0

Everything runs on one device, and the only network traffic is between Burrow and Ollama on the loopback address. An MCP client is drawn apart because it is a separate program that a person chooses to connect, and it may be a cloud service. When it is, what it reads leaves the Mac under that client's terms, and Burrow's privacy property then holds only for Burrow itself.
