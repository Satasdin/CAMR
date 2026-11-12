# Chapter 4:  System Analysis and Design

## 4.1 Introduction

This chapter presents the analysis and design of Burrow, the memory engine of this study, and addresses the second specific objective. The system was analysed and designed with Object-Oriented Analysis and Design (OOAD), as justified in Section 3.3, and the diagrams use the Unified Modeling Language (UML). Section 4.2 gives the requirements of the system. Section 4.3 presents the analysis diagrams, which are a use case diagram, two sequence diagrams, an activity diagram, and a class diagram. Section 4.4 presents the design diagrams, which are the system architecture, the engine's steps, the logical database schema, the wireframes, and a deployment diagram.

## 4.2 System Requirements

The system requirements identified for this project are presented in the following subsections. They were worked backwards from the specific objectives in Section 1.3 and from the Sprint II review of 5 November 2026. Each requirement has an identifier, a priority, the objective it serves, and the test case of Section 5.6 that verifies it. A requirement is marked Must when an objective depends on it and Should when it was added to strengthen the engine. No limit on response time was set in advance, because no measurement existed to justify one.

### 4.2.1 Functional Requirements

Table 4.1 lists the functional requirements. FR-01 to FR-03 cover the memory, FR-04 to FR-09 are the five steps of the engine, and FR-10 opens the engine to outside models.

!tab Table 4.1: Functional requirements
!widths 0.75,3.2,0.75,0.9,0.7
| ID | Requirement | Priority | Objective | Verified by |
| FR-01 | The engine shall index a vault of Markdown notes, documents, and linked code folders on the device, and later re-index only the files that changed. | Must | iii | TC-01 |
| FR-02 | The engine shall rank the pieces of the vault by word match and by meaning, and return excerpts with their file and line numbers within a character budget. | Must | ii | TC-02 |
| FR-03 | The engine shall follow the links between files for up to two hops from the best matches. | Must | ii | TC-03 |
| FR-04 | Decide: the engine shall judge from one search whether a question needs the vault, and whether to search or to follow links, and state the reason in words. | Must | ii | TC-04, TC-05 |
| FR-05 | Decide: the engine shall hand the model at most one skill, chosen by how closely it fits the question or else by the kind of material found. | Should | ii | TC-06 |
| FR-06 | Fit: the engine shall measure a local model once and set from that measurement how many characters the model is shown. | Must | ii, v | TC-07 |
| FR-07 | Answer: the engine shall have a local model answer from the excerpts, naming a file and line for each statement. | Must | iii | TC-08 |
| FR-08 | Check: the engine shall check every cited file and line against the excerpts shown, ask once more if a citation was not shown, and report any left unverified, on the command burrow ask --mode engine. | Should | ii | TC-09 |
| FR-09 | Learn: the engine shall propose at most three notes from a conversation, each backed by the person's own words, and in the terminal chat write a note only when the person accepts it. | Must | ii | TC-10 |
| FR-10 | The engine shall give the same decision, skill, and excerpts to an outside model through a command and through a Model Context Protocol (MCP) tool, without calling a chat model itself. | Should | iii | TC-11 |

### 4.2.2 Non-Functional Requirements

Table 4.2 lists the non-functional requirements. They cover privacy, durability, safety, cost, footprint, and portability, which are the qualities that matter for a memory kept on a person's own device. NFR-04 requires that cost be measured on every answer.

!tab Table 4.2: Non-functional requirements
!widths 0.75,3.2,0.75,0.9,0.7
| ID | Requirement | Priority | Objective | Verified by |
| NFR-01 | Privacy: the engine shall send notes and code only to the Ollama service on the same machine, at the loopback address 127.0.0.1. | Must | iii | TC-13 |
| NFR-02 | Durability: the person's files shall be the only lasting record, and the index shall be rebuilt from them if it is deleted. | Must | iii | TC-12 |
| NFR-03 | Safety: text from the vault shall be given to a model as material to read, with a rule that no instruction written inside it is followed. | Should | iii | TC-14 |
| NFR-04 | Cost: for every answer the engine shall report the tokens read, the tokens written, the seconds before the model was called, and the seconds the model took. | Must | iv | TC-15 |
| NFR-05 | Footprint: the index shall be one embedded database file inside the vault's .burrow folder, with no database server process. A rebuildable copy of its vectors and two small settings files sit beside it. | Must | iii | TC-16 |
| NFR-06 | Portability: the engine shall build as one Swift package with no third-party dependency, and its tests shall run with one command. | Should | iii | TC-17 |

### 4.2.3 Data Requirements

Table 4.3 lists the data requirements. They describe what the engine reads, what it stores, what it is allowed to write, and how the evaluation data is kept apart from the memory.

!tab Table 4.3: Data requirements
!widths 0.75,3.2,0.75,0.9,0.7
| ID | Requirement | Priority | Objective | Verified by |
| DR-01 | The input shall be a folder of plain Markdown files and linked code folders. The engine shall read these files and shall not change them. | Must | iii | TC-18 |
| DR-02 | For each piece of a file the index shall store its file, its first and last line, its text, and at most one embedding vector. | Must | iii | TC-19 |
| DR-03 | In the chat a note, and in the app a Ledger commit, shall be written only when the person accepts it, as a readable Markdown file in the vault. No write shall overwrite a note. Other writes are limited to the starter skills on request, accepted file changes, and notes added by burrow note, burrow learn, or an MCP client. | Must | ii | TC-10 |
| DR-04 | The evaluation questions and their answer keys shall be kept outside the vault, and the vault shall be built from the source documents only. | Must | iv | TC-20 |

### 4.2.4 Interface and Integration Requirements

Table 4.4 lists the interface and integration requirements. They describe how a person, the local model service, and outside tools meet the engine, and what happens when the model service fails.

!tab Table 4.4: Interface and integration requirements
!widths 0.75,3.2,0.75,0.9,0.7
| ID | Requirement | Priority | Objective | Verified by |
| IR-01 | The application shall show, for each conversation a connected program holds with the vault, every lookup and the files it read, each opening its file; the command line shall show under each answer what the engine decided, the skill it used, and the files it read. | Must | Sprint II | TC-08 |
| IR-02 | If the Ollama service cannot embed a question, the search shall continue on words alone. If it cannot answer, the failure shall be reported and no answer shown. | Must | iii | TC-21 |
| IR-03 | The MCP server shall exchange JSON-RPC messages over standard input and output, and shall offer its tools only after the client has initialised the session. | Should | iii | TC-11 |
| IR-04 | The vault shall stay a folder that Obsidian can open: plain Markdown with links written between double square brackets. | Should | iii | TC-22 |
| IR-05 | The system shall be offered from a public landing page, with the terminal version installed by one command and the desktop application downloaded by one click, both from the project's published releases. | Should | Sprint II | TC-23 |

## 4.3 System Analysis Diagrams

This section presents the diagrams used to analyse the actors, the behaviour, and the structure of the system. Each diagram is introduced, shown, and then interpreted.

### 4.3.1 Use Case Diagram

The use case diagram gives the widest view of the system, namely who uses Burrow and for what. It was chosen because the engine serves three kinds of actor, and it addresses requirements FR-04 to FR-10. Figure 4.1 shows the boundary of the system and its actors: the person who owns the vault, the local model served by Ollama, and an outside model or tool that brings its own model.

!fig figures/v2/use_cases.png | Figure 4.1: Use case diagram of Burrow | 6.2

Asking a question and preparing a task for another model both include the same use case, deciding and packing the excerpts, so the engine's judgement is shared by every way of using it. Only the path of the local model includes checking the citations, because only there does the engine see the answer. Table 4.5 describes the use case that carries the study, "Ask a question", which exercises four of the five steps.

!tab Table 4.5: Use case description: Ask a question
!widths 1.4,4.9
| Item | Description |
| Actors | Person (primary), local model (supporting) |
| Precondition | The vault has been indexed. Ollama is running with a chat model. |
| Main flow | 1. The person asks a question. 2. The engine searches once and decides: leave the vault out, search, or follow links. 3. The engine picks a skill and packs the excerpts within the model's budget. 4. The local model answers. 5. The engine checks each file and line cited. 6. The person receives the answer, the decision line, and the sources. |
| Alternative flows | At step 2 nothing in the vault is close, so the model answers without excerpts. At step 5, on the command line, a citation was not among the excerpts, so the model is asked once more and the better grounded answer is kept. |
| Exceptions | Ollama cannot embed the question, so ranking continues on words alone. Ollama cannot answer, so the failure is reported and no answer is shown. |
| Postcondition | No file in the vault has changed. Any citation that could not be verified is named. |

### 4.3.2 Sequence Diagrams

A sequence diagram shows the order of the messages between the parts of the system. It was chosen because the five steps must run in a fixed order, and the first diagram addresses FR-04 to FR-08. Figure 4.2 shows the messages exchanged when a person asks a question through the engine.

!fig figures/v2/sequence_engine.png | Figure 4.2: Sequence diagram of a question asked through the engine | 5.6

The model profile is fetched first, so the budget is known before any search begins. The local model is called once in the usual case and twice at most, the second time with the wrongly cited places named. Figure 4.3 shows the second way in, which addresses FR-10: an outside model using Burrow through the MCP tool vault_prepare.

!fig figures/v2/sequence_mcp.png | Figure 4.3: Sequence diagram of an outside model preparing a task through MCP | 5.6

The only model Burrow calls on this path is the embedding model. The outside model receives the decision, a skill, and the excerpts, and writes the answer itself. Burrow therefore never sees that answer and cannot check its citations.

### 4.3.3 Activity Diagram

The activity diagram shows the decisions of the engine's loop and who makes each one. It was chosen because the study depends on separating what the engine decides from what the model writes, and it addresses FR-04 to FR-09. Figure 4.4 follows the loop from a question to a kept note, in three swimlanes for the person, the engine, and the local model.

!fig figures/v2/activity.png | Figure 4.4: Activity diagram of the engine's loop | 5.3

Every choice about what the model reads is made in the engine lane, before the model is called. Each time the model returns something, the engine examines it before it is used. The last decision belongs to the person, who accepts or declines each proposed note.

### 4.3.4 Class Diagram

The class diagram shows the types of the engine and how they depend on one another. It was chosen because it maps directly to the Swift code and guided how the library was divided. Figure 4.5 shows the main types as they were built.

!fig figures/v2/classes.png | Figure 4.5: Class diagram of the engine | 6.2

The Vault type is the single entry point: brief decides and packs, engage adds the answer and the check, and lessons and keep are the two halves of Learn. A Brief contains no answer, which is why it can be handed to an outside model. Embedder and Answerer are protocols, so the tests run the whole loop with a scripted model in place of a real one.

## 4.4 System Design Diagrams

This section presents the diagrams that show how the system was organised to satisfy the analysed requirements.

### 4.4.1 System Architecture

The architecture diagram shows the components of Burrow and which component depends on which. It was chosen to show that all memory logic sits in one library that every surface uses, and it addresses FR-10 and NFR-06. Figure 4.6 shows the components in three layers: the surfaces that a person or a tool touches, a shared set of tools, and the core.

!fig figures/v2/architecture.png | Figure 4.6: Architecture of Burrow | 6.2

All memory logic is in BurrowCore, and every surface depends on it, so a change to the engine reaches the application, the terminal chat, and the MCP server at once. The Ollama client is the only part that leaves the process. Which steps each surface runs is recorded in Section 5.4.6.

### 4.4.2 Engine Steps and Retrieval Design

Objective ii names three mechanisms: a write policy, a retrieval policy, and a token budgeting mechanism. Figure 4.7 shows the five steps of the engine, what each reads and writes, and how the steps map to those mechanisms.

!fig figures/v2/engine_steps.png | Figure 4.7: The five steps of the engine and the three mechanisms of objective ii | 6.2

Learn is the write policy, Decide and the retrieval behind it are the retrieval policy, and Fit is the token budgeting mechanism. Check was added in this study. Ranking is by words, meaning, and links, and the recency and importance scores named in objective ii decide between files that match a question equally well, so they never overrule relevance.

Retrieval ranks each piece twice, by word match with BM25 (Robertson & Zaragoza, 2009) and by meaning. Meaning is the cosine between the vector of the question, q, and the vector of a piece, v, as in Equation 4.1.

!eq cosine | Equation 4.1: Cosine similarity between a question and a piece

The two rankings are merged by reciprocal rank fusion (Cormack et al., 2009), as in Equation 4.2, where the rank of piece p in ranking r counts from 1 and w(p) lowers the weight of test files and of the output of past runs. Pieces holding an exact name from the question, or from a file the question names, are placed before this ranking.

!eq rrf | Equation 4.2: Merged score of a piece

When links are followed, a neighbouring file n is ranked by Equation 4.3, where b(n) is its word match scaled so that the best file scores 1, h is the hop number, and k(n) depends on the kind of link.

!eq walk | Equation 4.3: Score of a neighbouring file during a walk

### 4.4.3 Logical Database Schema

The index is the only database in the system, and it holds no original data. The schema was chosen as a design view because its tables decide what can be searched by words, by meaning, and by links, and it addresses DR-02 and NFR-02. Figure 4.8 shows its logical schema, which is one SQLite database.

!fig figures/v2/schema.png | Figure 4.8: Logical schema of the index | 6.2

A file is cut into pieces stored as chunks, and a piece has at most one vector, because the index also works on words alone. The chunks_fts table is the full-text index, and the links table holds the links between files. Nothing in the schema is a source of truth: the whole index can be rebuilt from the Markdown files, which satisfies NFR-02.

### 4.4.4 Wireframes

The wireframes plan where the person sees what the engine and the models that use it did, which addresses IR-01 and the Sprint II request for something a person can see and use. They follow the application as built after 11 November 2026, when its own question box gave way to the programs that connect to the vault, because the vault is the memory and the chat belongs to those programs. Figure 4.9 is the main window on a conversation that a connected program held with the vault.

!fig figures/v4/wire_main.png | Figure 4.9: Wireframe of the main window on a conversation a connected program held with the vault | 6.0

Each step on the trail is one lookup the model made, in the model's own words, followed by a card for every file it read, and each card opens its file. The narrow strip on the left switches between the pages of the vault, and the status bar counts the notes, files, links, conversations and Ledger commits. Figure 4.10 is the note editor, where a note is a plain Markdown file, its properties are shown as fields, and a link to another note is written between double square brackets.

!fig figures/v4/wire_editor.png | Figure 4.10: Wireframe of the note editor with its properties and links | 6.0

The panel on the right shows the note's neighbours as a small graph and lists the notes that link to it, the notes that name it without a link, its outline, and what models have understood about it. These links are the ones the engine follows in FR-03. Figure 4.11 is the step where the person keeps a decision from a conversation in the Ledger, which addresses DR-03 in the application.

!fig figures/v4/wire_keep.png | Figure 4.11: Wireframe of keeping a decision from a conversation in the Ledger | 6.0

Nothing is kept unless the person writes the sentence and presses Keep, and the kept commit cites the files the conversation read, so it goes stale when one of them changes. Figure 4.12 is the terminal chat, which shows the engine's decision under each question and proposes notes through Learn.

!fig figures/v2/wire_terminal.png | Figure 4.12: Wireframe of the terminal chat | 6.0

The line under each question is the engine's decision, and the /keep command offers each note in turn and waits for a yes before it writes.

### 4.4.5 Deployment Diagram

The deployment diagram shows where each part runs and how a person obtains the system. It was chosen because it allows the privacy requirement NFR-01 to be inspected, and because it shows the distribution path of IR-05. Figure 4.13 shows the person's computer, the two connections that can leave it during use, and the place the software is downloaded from.

!fig figures/v2/deployment.png | Figure 4.13: Deployment diagram of Burrow | 6.0

The application, the command-line tool, the vault, the index, and the local models are on the person's own computer, and the engine reaches the local model service only on the loopback address. Neither of the two outside connections is made by the engine. One is an MCP client that the person chooses to connect, and the other is the evaluation harness calling the cloud model.

A person obtains the system once, from a tagged release of the project's repository, so the version installed is the one the repository records; the steps are given in Section 5.2.3. The download carries no content from the vault, so after installation the engine works offline.

Chapter 5 describes how this design was implemented, tested, and evaluated.
