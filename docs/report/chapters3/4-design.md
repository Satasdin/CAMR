# Chapter 4:  System Analysis and Design

## 4.1 Introduction

This chapter presents the analysis and design of Burrow, the memory engine of this study. It gives the functional and non-functional requirements, and then the diagrams named in Chapter 3. The work followed Object-Oriented Analysis and Design, and the diagrams use the Unified Modeling Language (UML). One idea runs through the chapter: the engine takes five steps around a frozen local model, which are Decide, Fit, Answer, Check, and Learn.

## 4.2 System Requirements

The requirements were worked backwards from the objectives in section 1.3 and from the three mechanisms of the proposal: a write policy, a retrieval policy, and a token budgeting mechanism. The test cases of Chapter 5 refer to the identifiers given here.

### 4.2.1 Functional Requirements

Table 4.1 lists the ten functional requirements. FR-01 to FR-03 cover the memory, FR-04 to FR-09 are the five steps of the engine, and FR-10 opens the engine to outside models.

!tab Table 4.1: Functional requirements
!widths 0.8,5.5
| ID | Requirement |
| FR-01 | The engine shall index a vault of Markdown notes, documents, and linked code folders on the device, and later re-read only the files that changed. |
| FR-02 | The engine shall rank the pieces of the vault by word match and by meaning, and return excerpts with their file and line numbers within a character budget. |
| FR-03 | The engine shall follow the links between files for up to two hops from the best matches. |
| FR-04 | Decide: the engine shall judge from one search whether a question needs the vault, and whether to search or to follow links, and state the reason in words. |
| FR-05 | Decide: the engine shall hand the model at most one skill, chosen by how closely it fits the question or else by the kind of material found. |
| FR-06 | Fit: the engine shall measure a local model once and set from that measurement how many characters the model is shown. |
| FR-07 | Answer: the engine shall have a local model answer from the excerpts, naming a file and line for each statement. |
| FR-08 | Check: the engine shall check every cited file and line against the excerpts shown, ask once more if a citation was not shown, and report any left unverified. |
| FR-09 | Learn: the engine shall propose at most three notes from a conversation, each backed by the person's own words, and write a note only when the person accepts it. |
| FR-10 | The engine shall give the same decision, skill, and excerpts to an outside model through a command and through a Model Context Protocol (MCP) tool, without calling a chat model itself. |

### 4.2.2 Non-Functional Requirements

Table 4.2 lists the six non-functional requirements. No limit on response time was set in advance, so NFR-04 requires that cost be measured on every answer.

!tab Table 4.2: Non-functional requirements
!widths 0.8,5.5
| ID | Requirement |
| NFR-01 | Privacy: the engine shall send notes and code only to the Ollama service on the same machine, at the loopback address 127.0.0.1. |
| NFR-02 | Durability: the person's files shall be the only lasting record, and the index shall be rebuilt from them if it is deleted. |
| NFR-03 | Safety: text from the vault shall be given to a model as material to read, with a rule that no instruction written inside it is followed. |
| NFR-04 | Cost: for every answer the engine shall report the tokens read, the tokens written, the seconds before the model was called, and the seconds the model took. |
| NFR-05 | Footprint: the index shall be one embedded database file inside the vault's `.burrow` folder, with no database server process. |
| NFR-06 | Portability: the engine shall build as one Swift package with no third-party dependency, and its tests shall run with one command. |

## 4.3 System Analysis Diagrams

### 4.3.1 Use Case Diagram

Figure 4.1 shows the boundary of the system and its three kinds of actor: the person who owns the vault, the local model served by Ollama, and an outside model or tool that brings its own model. Asking a question and preparing a task for another model both include the same use case, deciding and packing the excerpts. Only the path of the local model includes checking the citations, because only there does the engine see the answer.

!fig figures/v2/use_cases.png | Figure 4.1: Use case diagram of Burrow. | 5.2

### 4.3.2 Use Case Description

Table 4.3 describes the use case that carries the study, "Ask a question". It exercises four of the five steps: Decide, Fit, Answer, and Check.

!tab Table 4.3: Use case description: Ask a question
!widths 1.4,4.9
| Item | Description |
| Actors | Person (primary), local model (supporting) |
| Precondition | The vault has been indexed. Ollama is running with a chat model. |
| Main flow | 1. The person asks a question. 2. The engine searches once and decides: leave the vault out, search, or follow links. 3. The engine picks a skill and packs the excerpts within the model's budget. 4. The local model answers. 5. The engine checks each file and line cited. 6. The person receives the answer, the decision line, and the sources. |
| Alternative flows | At step 2 nothing in the vault is close, so the model answers without excerpts. At step 5 a citation was not among the excerpts, so the model is asked once more and the better grounded answer is kept. |
| Exceptions | Ollama cannot embed the question, so ranking continues on words alone. Ollama cannot answer, so the failure is reported and no answer is shown. |
| Postcondition | No file in the vault has changed. Any citation that could not be verified is named. |

### 4.3.3 Sequence Diagram

Figure 4.2 shows the messages exchanged when a person asks a question through the engine. The model profile is fetched first, so the budget is known before any search begins. The local model is called once in the usual case and twice at most, the second time with the wrongly cited places named.

!fig figures/v2/sequence_engine.png | Figure 4.2: Sequence diagram of a question asked through the engine. | 5.4

Figure 4.3 shows an outside model using Burrow through the MCP tool `vault_prepare`. The only model Burrow calls is the embedding model. The outside model receives the decision, a skill, and the excerpts, and writes the answer itself.

!fig figures/v2/sequence_mcp.png | Figure 4.3: Sequence diagram of an outside model preparing a task through MCP. | 5.4

### 4.3.4 Activity Diagram

Figure 4.4 follows the engine's loop from a question to a kept note, in three swimlanes for the person, the engine, and the local model. Every choice about what the model reads is made in the engine lane, before the model is called. Each time the model returns something, the engine examines it before it is used.

!fig figures/v2/activity.png | Figure 4.4: Activity diagram of the engine's loop. | 4.8

### 4.3.5 Class Diagram

Figure 4.5 shows the main types of the engine as they were built. `Vault` is the single entry point: `brief` decides and packs, `engage` adds the answer and the check, and `lessons` and `keep` are the two halves of Learn. A `Brief` contains no answer, which is why it can be handed to an outside model. `Embedder` and `Answerer` are protocols, so the tests run the whole loop with a scripted model.

!fig figures/v2/classes.png | Figure 4.5: Class diagram of the engine. | 5.8

## 4.4 System Design Diagrams

### 4.4.1 System Architecture

Figure 4.6 shows the components of Burrow in three layers: the surfaces that a person or a tool touches, a shared set of tools, and the core. All memory logic is in BurrowCore, and every surface depends on it. The Ollama client is the only part that leaves the process.

!fig figures/v2/architecture.png | Figure 4.6: Architecture of Burrow. | 5.8

Figure 4.7 shows the five steps of the engine and what each reads and writes. The steps map to the mechanisms of the proposal. Learn is the write policy, Decide and the retrieval behind it are the retrieval policy, and Fit is the token budgeting mechanism. Check was added in this study. The recency and importance scores of the proposal were not built, and ranking is by words, meaning, and links.

!fig figures/v2/engine_steps.png | Figure 4.7: The five steps of the engine and the mechanisms of the proposal. | 6.0

Retrieval ranks each piece twice, by word match with BM25 (Robertson & Zaragoza, 2009) and by meaning. Meaning is the cosine between the vector of the question, q, and the vector of a piece, v, as in Equation 4.1.

!eq cosine | Equation 4.1: Cosine similarity between a question and a piece.

The two rankings are merged by reciprocal rank fusion (Cormack et al., 2009), as in Equation 4.2, where the rank of piece p in ranking r counts from 1 and w(p) lowers the weight of test files and of the output of past runs.

!eq rrf | Equation 4.2: Merged score of a piece.

When links are followed, a neighbouring file n is ranked by Equation 4.3, where b(n) is its word match scaled so that the best file scores 1, h is the hop number, and k(n) depends on the kind of link.

!eq walk | Equation 4.3: Score of a neighbouring file during a walk.

### 4.4.2 Database Schema

Figure 4.8 shows the logical schema of the index, which is one SQLite file. A file is cut into pieces stored as `chunks`, and a piece has at most one vector, because the index also works on words alone. `chunks_fts` is the full-text table, and `links` holds the links between files. Nothing in the schema is a source of truth: the whole index can be rebuilt from the Markdown files.

!fig figures/v2/schema.png | Figure 4.8: Logical schema of the index. | 5.8

### 4.4.3 Wireframes

Figure 4.9 is the main window of the Mac application with the Ask panel open. The decision line sits directly under the answer and says whether the vault was read, why, and which skill was handed to the model. A warning line appears only when the answer cites a place the model was not shown.

!fig figures/v2/wire_main.png | Figure 4.9: Wireframe of the main window with the Ask panel. | 5.2

Figure 4.10 is the note editor. A note is a plain Markdown file, and a link to another note is written between double square brackets, with the matching names offered as it is typed. The panel on the right shows the note's neighbours as a small graph and lists the notes that link to it and the files it links to.

!fig figures/v3/wire_editor.png | Figure 4.10: Wireframe of the note editor with its links. | 5.2

Figure 4.11 is the step where the person agrees to what is kept. The engine offers at most three notes, each with its kind and one sentence. Each note has its own Keep button, so nothing is written to the vault without an act of the person. A kept note appears as a new file in the Memory folder.

!fig figures/v3/wire_keep.png | Figure 4.11: Wireframe of the step where the person keeps what was decided. | 5.2

Figure 4.12 is the terminal chat, started with `burrow chat`. It shows the same two moments as the window. The line under each question is the engine's decision, and the `/keep` command offers each note in turn and waits for a yes before it writes.

!fig figures/v2/wire_terminal.png | Figure 4.12: Wireframe of the terminal chat. | 5.2

### 4.4.4 Deployment Diagram

Figure 4.13 shows where each part runs. The application, the command-line tool, the vault, the index, and both local models are on one laptop, and the engine reaches Ollama only on the loopback address. Two connections leave the laptop, and neither is made by the engine: an MCP client that the person chooses to connect, and the evaluation harness calling the cloud model.

!fig figures/v2/deployment.png | Figure 4.13: Deployment diagram of Burrow. | 5.2
