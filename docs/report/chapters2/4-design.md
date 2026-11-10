# Chapter 4:  System Analysis and Design

## 4.1 Introduction

This chapter presents the analysis and design of Burrow, the memory engine of this study. It states what the engine had to do, shows who uses it and how, and then shows how it was put together.

The engine was written in Swift as a set of types that hold their own data and behaviour, so the chapter follows Object-Oriented Analysis and Design and uses the Unified Modeling Language (UML). Section 4.2 gives the requirements. Section 4.3 gives the analysis diagrams: one use case diagram with two use case descriptions, one activity diagram, and two sequence diagrams. Section 4.4 gives the design diagrams: the architecture, the design of the engine's five steps, a class diagram, a state machine, the database schema, two wireframes, and a deployment diagram.

One idea runs through the whole chapter. The engine takes five steps around a frozen local model: Decide, Fit, Answer, Check, and Learn. Every requirement and every diagram describes one or more of these steps.

## 4.2 System Requirements

The requirements were worked backwards from the objectives in section 1.3 and from the mechanisms promised in the proposal: a write policy, a retrieval policy, and a token budgeting mechanism. Each requirement has an identifier, one statement, and the way it is verified. Chapter 5 refers to these identifiers in its test cases.

### 4.2.1 Functional Requirements

Table 4.1 lists the ten functional requirements. FR-01 to FR-03 cover the memory itself. FR-04 to FR-09 are the five steps of the engine. FR-10 opens the engine to models that Burrow does not host.

!tab Table 4.1: Functional requirements
!widths 0.7,4.5,1.1
| ID | Requirement | Verified by |
| FR-01 | The engine shall index a vault of Markdown notes, documents, and linked code folders into a database on the device, and on later runs shall re-read only the files that changed. | Test |
| FR-02 | The engine shall rank the pieces of the vault by word match and by meaning, merge the two rankings, and return excerpts with their file and line numbers within a character budget. | Test |
| FR-03 | The engine shall follow the links between files for up to two hops from the best matches. | Test |
| FR-04 | Decide: the engine shall judge from one search whether a question needs the vault, and whether to search or to follow links, and shall state its decision and the reason in words. | Test |
| FR-05 | Decide: the engine shall hand the model at most one skill, a short written method, chosen by how closely the skill fits the question or else by the kind of material found. | Test |
| FR-06 | Fit: the engine shall measure a local model once, and from its reading speed, its size, and its characters per token shall set how many characters that model is shown. | Test |
| FR-07 | Answer: the engine shall have a local model answer from the excerpts, under rules that require a file and line for each statement. | Test |
| FR-08 | Check: the engine shall check every file and line an answer cites against the excerpts shown, ask the model once more if a citation was not shown, and report any citation left unverified. | Test |
| FR-09 | Learn: the engine shall propose at most three notes from a conversation, each backed by a quote found in the person's own words, and shall write a note only when the person accepts it. | Test |
| FR-10 | The engine shall give the same decision, skill, and excerpts to an outside model, through a command and through a Model Context Protocol (MCP) tool, without calling a chat model itself. | Test |

### 4.2.2 Non-Functional Requirements

Table 4.2 lists the six non-functional requirements. No limit on response time was set in advance, because nothing in the study justified a particular number. NFR-04 therefore requires that cost be measured on every answer, and Chapter 5 reports what was measured.

!tab Table 4.2: Non-functional requirements
!widths 0.7,4.5,1.1
| ID | Requirement | Verified by |
| NFR-01 | Privacy: the engine shall send notes and code only to the Ollama service on the same machine, at the loopback address 127.0.0.1. | Inspection |
| NFR-02 | Durability: the person's files shall be the only lasting record. Deleting the index shall lose no note, and the next indexing run shall rebuild it. | Test |
| NFR-03 | Safety: text taken from the vault shall be given to a model as material to read, with a rule that no instruction written inside it is followed. | Test |
| NFR-04 | Cost: for every answer the engine shall report the tokens read, the tokens written, the seconds spent before the model was called, and the seconds the model took. | Measurement |
| NFR-05 | Footprint: the index shall be one embedded database file inside the vault's `.burrow` folder, with no database server process. | Inspection |
| NFR-06 | Portability: the engine shall build as one Swift package with no third-party dependency, and its tests shall run with one command. | Demonstration |

## 4.3 System Analysis Diagrams

This section shows who uses the engine, what they use it for, and in what order things happen. The diagrams were drawn from the script `docs/report/figures/diagrams2.py`, which is kept as their editable source.

### 4.3.1 Use Case Diagram

Figure 4.1 shows the boundary of the system and its actors. There are three kinds of actor. The person is a developer or a student who owns the vault. The local model is the frozen model served by Ollama. An outside model or tool is any program that brings its own model, such as Claude Code over MCP or a LangChain pipeline. The cloud model used in the evaluation is one such outside model, which the diagram shows as a generalisation.

!fig figures/v2/use_cases.png | Figure 4.1: Use case diagram of Burrow. | 5.6

The diagram makes one design point visible. Asking a question and preparing a task for another model both include the same use case, deciding and packing the excerpts. The engine therefore serves a model it hosts and a model it does not host with the same code. Only the hosted path includes checking the citations, because only there does the engine see the answer.

### 4.3.2 Use Case Descriptions

Tables 4.3 and 4.4 describe the two use cases that carry the study: asking a question, which exercises Decide, Fit, Answer, and Check, and keeping what a conversation decided, which is Learn.

!tab Table 4.3: Use case description: Ask a question
!widths 1.4,4.9
| Item | Description |
| Actors | Person (primary), local model (supporting) |
| Requirements | FR-02 to FR-08, NFR-01, NFR-03, NFR-04 |
| Precondition | The vault has been indexed. Ollama is running with a chat model. |
| Main flow | 1. The person asks a question. 2. The engine searches once and decides: leave the vault out, search, or follow links. 3. The engine picks a skill and packs the excerpts within the model's budget. 4. The local model answers. 5. The engine checks each file and line cited. 6. The person receives the answer, the decision line, and the sources. |
| Alternative flows | At step 2 nothing in the vault is close, so the model answers without excerpts. At step 5 a citation was not among the excerpts, so the model is asked once more, and the better grounded of the two answers is kept. |
| Exceptions | Ollama cannot embed the question, so ranking continues on words alone. Ollama cannot answer, so the failure is reported and no answer is shown. |
| Postcondition | No file in the vault has changed. Any citation that could not be verified is named. |

!tab Table 4.4: Use case description: Keep what a conversation decided
!widths 1.4,4.9
| Item | Description |
| Actors | Person (primary), local model (supporting) |
| Requirements | FR-09, NFR-02 |
| Precondition | A conversation of at least one question and answer has taken place. |
| Main flow | 1. The person asks for the conversation to be kept. 2. The engine asks the model what the person decided, with the person's exact words for each item. 3. The engine drops any item whose quote the person never typed, and any item the vault already holds. 4. The engine shows each remaining note to the person. 5. The person accepts or declines each one. 6. The engine writes each accepted note as a Markdown file and brings the index up to date. |
| Alternative flows | At step 3 nothing remains, so the person is told there is nothing new to keep. |
| Exceptions | Nobody is at the keyboard, so nothing is offered and nothing is written. |
| Postcondition | The vault holds one new note for each item the person accepted, and no other change. |

### 4.3.3 Activity Diagram

Figure 4.2 follows the engine's loop from a question to a kept note. The three swimlanes separate what the person does, what the engine does, and what the local model does.

!fig figures/v2/activity.png | Figure 4.2: Activity diagram of the engine's loop. | 5.5

Two things in the diagram matter for the rest of the report. First, every choice about what the model reads is made in the engine lane, before the model is called. The model reads and writes, and it selects nothing. Second, the model appears three times, and each time the engine examines what comes back: the answer is checked against the excerpts, the second answer is kept only if it is better grounded, and a proposed note is dropped unless the person really said it.

### 4.3.4 Sequence Diagrams

Figure 4.3 shows the messages exchanged when a person asks a question from the command line with `burrow ask --mode engine`. It covers FR-04 to FR-08.

!fig figures/v2/sequence_engine.png | Figure 4.3: Sequence diagram of a question asked through the engine. | 5.8

The model profile is fetched before the question is engaged, so the budget is known before any search begins. The local model is called once in the usual case and twice at most. The second call sends the same prompt with a correction that names the places the first answer wrongly cited. The Mac application takes the same steps up to the check and shows unverified citations as a warning, but it does not ask again.

Figure 4.4 shows an outside model using Burrow through the MCP tool `vault_prepare`. It covers FR-10.

!fig figures/v2/sequence_mcp.png | Figure 4.4: Sequence diagram of an outside model preparing a task through MCP. | 5.8

The only model Burrow calls in this sequence is the embedding model. The outside model receives the decision line, a method if one fits, and the excerpts marked as data, and it writes the answer itself. The engine cannot check that answer, because it never sees it. For an outside model the budget is a fixed number of characters and is not fitted, because Burrow cannot measure a model it does not host.

## 4.4 System Design Diagrams

This section shows how the engine was organised to meet the requirements.

### 4.4.1 System Architecture

Figure 4.5 shows the components and their main dependencies. The design has three layers: the surfaces that a person or a tool touches, a shared set of tools, and the core that holds the engine.

!fig figures/v2/architecture.png | Figure 4.5: Architecture of Burrow. | 5.8

All memory logic is in one component, BurrowCore, and every surface depends on it. The eight tools are defined once in BurrowTools, so the terminal chat and an MCP client cannot be given different behaviour. The Ollama client is the only part that leaves the process, which makes NFR-01 a matter of inspecting one file. The evaluation harness is not in the figure because it is not part of the product. It drives the `burrow` command from outside.

### 4.4.2 Engine Design

Figure 4.6 shows the five steps of the engine, what the proposal called each one, and what each reads and writes.

!fig figures/v2/engine_steps.png | Figure 4.6: The five steps of the engine and the mechanisms of the proposal. | 6.0

**Retrieval.** A question is ranked twice. Word search uses BM25 over the paths and text of the pieces (Robertson & Zaragoza, 2009). Meaning uses the cosine between the vector of the question, q, and the vector of each piece, v, as in Equation 4.1. All vectors are stored as one block of unit vectors mapped into memory, so the whole vault is compared in a single matrix multiplication.

!eq cosine | Equation 4.1: Cosine similarity between a question and a piece.

The two rankings are merged by reciprocal rank fusion (Cormack et al., 2009), as in Equation 4.2. The rank of piece p in each ranking r counts from 1. The weight w(p) is 1 for ordinary files, 0.7 for test files, and 0.4 for the output of past runs, because those files repeat the words of the code they are about.

!eq rrf | Equation 4.2: Merged score of a piece.

When links are followed, the best piece of each of the first few files is taken as a starting point, using at most 60% of the budget. A neighbouring file n is then ranked by Equation 4.3. Here b(n) is its word match scaled so that the best file scores 1, h is the hop number, and k(n) depends on the link: 3 when a note is about the file, 1 for an import, and 0.75 for a name that is used, with lower values in the reverse direction.

!eq walk | Equation 4.3: Score of a neighbouring file during a walk.

This is a change from the proposal. The proposal ranked by similarity, recency, and importance after Park et al. (2023). The recency and importance scores were not built, and ranking is by words, meaning, and links.

**Decide.** One plain search gives a signal with two numbers: the closeness of the nearest piece and the number of pieces that share a word with the question. Table 4.5 gives the rules applied to that signal, in order. The thresholds were set on development questions before any scored run.

!tab Table 4.5: Rules of the Decide step, applied in order
!widths 3.6,2.7
| Condition | Decision |
| The search returns nothing, or the nearest piece is below 0.40 | Leave the vault out |
| The nearest piece is below 0.52, and a skill that needs no vault fits the question better | Leave the vault out |
| There are no vectors and no piece shares a word with the question | Leave the vault out |
| At least half of the four closest files are code | Follow links (walk) |
| Otherwise | Plain search |

A skill is a Markdown file in the vault's `Skills` folder that says how to do one kind of task. Nine starter skills are supplied, and a person can edit them or add more. A skill is matched only when its description is at least 0.55 close to the question and at least 0.10 clear of the next skill. When none stands out, a fallback is chosen by the material: one skill for documents and one for code.

**Fit.** The first time a model is used, the engine asks Ollama for its size and context length, and times it reading one page and writing one line. The budget is the smallest of three limits: a ceiling for the model's size, from 8,000 characters below 3 billion parameters to 32,000 above 20 billion; what the model can read in eight seconds; and what fits in its context after 2,600 tokens are kept back for the rules, the skill, the question, and the answer. The profile is saved with the vault, so the measurement is made once.

**Answer.** The model receives the rules, the skill, the numbered excerpts, and the question. The rules tell it to use only the excerpts, to name a file and line for each statement, to say when the answer is not there, and to follow no instruction written inside an excerpt. The model's weights are never changed.

**Check.** The engine reads every `file:line` in the answer and marks it as shown only if that line of that file was among the excerpts. If any citation was not shown, the model is asked once more with the wrong places named. The second answer replaces the first only if it has fewer unverified citations.

**Learn.** After a conversation the model is asked what the person decided, and must give the person's exact words for each item. The engine keeps an item only if that quote appears in what the person typed, so the model cannot turn its own guess into a remembered fact. Section 4.4.4 follows one such note to its end.

### 4.4.3 Class Diagram

Figure 4.7 shows the main types of the engine as they were built.

!fig figures/v2/classes.png | Figure 4.7: Class diagram of the engine. | 6.1

`Vault` is the single entry point, and its methods are the steps of the engine: `brief` decides and packs, `engage` adds the answer and the check, and `lessons` and `keep` are the two halves of Learn. A `Brief` is everything a model needs for one question and contains no answer, which is why it can be handed to a model Burrow does not host. An `EngineReply` wraps a brief with the answer and its citations. `Embedder` and `Answerer` are protocols, so the tests run the whole loop with a scripted model and without Ollama.

### 4.4.4 State Machine Diagram

A proposed note is the one object in the system whose history decides whether the vault changes, so Figure 4.8 shows its states. It supports FR-09.

!fig figures/v2/states.png | Figure 4.8: State machine diagram of a proposed note. | 6.0

A note reaches the vault by one path only, and that path has two gates. The first gate is the engine's: the quote must be the person's own words, and the note must be new. The second gate is the person's: each note is accepted or declined by itself. A note that fails the first gate is never shown.

### 4.4.5 Database Schema

Figure 4.9 shows the logical schema of the index, which is one SQLite file. It supports FR-01 and FR-02, NFR-02, and NFR-05.

!fig figures/v2/schema.png | Figure 4.9: Logical schema of the index. | 6.0

A file is cut into pieces, stored as `chunks`, and a piece has at most one vector, because the index also works on words alone. `chunks_fts` is the full-text table and shares its row numbers with `chunks`. `links` refers to files by path, because every link is deleted and rebuilt on each indexing run. `meta` holds a generation counter that rises whenever the pieces change. The block of vectors beside the database carries the generation it was built for, and a block from another generation is rebuilt before it is used. Nothing in the schema is a source of truth: the notes are Markdown files in the vault, and the whole index can be rebuilt from them.

### 4.4.6 User Interface Wireframes

Two surfaces show the engine to a person. Figure 4.10 is the main window of the Mac application with the Ask panel open.

!fig figures/v2/wire_main.png | Figure 4.10: Wireframe of the main window with the Ask panel. | 6.0

The decision line sits directly under the answer. It says in words whether the vault was read, why, and which method was handed to the model, so the person can see what the engine did without opening a log. A warning line appears only when the answer cites a place the model was not shown. Each proposed note has its own Keep button, so nothing is written to the vault without an act of the person.

Figure 4.11 is the terminal chat, started with `burrow chat`.

!fig figures/v2/wire_terminal.png | Figure 4.11: Wireframe of the terminal chat. | 6.0

The terminal shows the same two moments as the window. The line under each question is the engine's decision, printed before the answer begins. The `/keep` command offers each note in turn and waits for a yes before it writes.

### 4.4.7 Deployment Diagram

Figure 4.12 shows where each part runs. It supports NFR-01 and NFR-05.

!fig figures/v2/deployment.png | Figure 4.12: Deployment diagram of Burrow. | 5.8

The application, the command-line tool, the vault, the index, and both models are on one laptop, and the engine reaches Ollama only on the loopback address. Two connections leave the laptop, and neither is made by the engine. An MCP client that the person chooses to connect may send what it reads to its own provider. The evaluation harness calls the cloud model for the ceiling condition of Chapter 3.
