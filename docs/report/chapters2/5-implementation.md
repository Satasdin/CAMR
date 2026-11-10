# Chapter 5:  System Implementation, Testing and Evaluation

## 5.1 Introduction

This chapter shows the engine as it was built, how it was tested, and what the experiments measured. Section 5.2 states the environment. Section 5.3 presents the implemented engine with its screens and code. Section 5.4 gives the test cases and their results. Section 5.5 reports the experiments that answer the research questions, and Section 5.6 discusses them against each objective. Every number in this chapter was produced by a script from saved answers, and the scripts are in the repository beside the results.

## 5.2 Implementation Environment

Burrow was built and tested on one laptop. Nothing in its operation leaves that laptop: the models run in Ollama on the same machine, and the cloud model was called only by the evaluation harness.

### 5.2.1 Hardware and Deployment Environment

Table 5.1 states the machine used. It is the only configuration tested, so it is not a proven minimum.

!tab Table 5.1: Hardware and deployment environment
!widths 1.5,3.0,1.8
| Item | Specification | Purpose |
| Laptop | Apple MacBook Pro, M5 Pro chip, 24 GB shared memory, internal SSD | Runs the engine, the index and the local models |
| Operating system | macOS 27.2 | Required by the app's interface libraries |
| Model runner | Ollama 0.40.14 at 127.0.0.1:11434 | Hosts the frozen local models on the device |
| Network | Needed only to download models and to call the cloud model during evaluation | The engine itself works offline |
| Server | None | The index is one embedded database file |

### 5.2.2 Software, Services and Configuration

Table 5.2 records the software and the models. The engine has no third-party Swift dependency. The evaluation harness is separate from the engine and is the only part written in Python.

!tab Table 5.2: Software, models and settings
!widths 1.6,1.9,2.8
| Component | Version | Role |
| Swift and Xcode | Swift 6.4.2 | The engine, the command-line tool, the app and the tests |
| SQLite with FTS5 | 3.54.0, supplied with macOS | The embedded index: word search, vectors and links |
| Accelerate | Supplied with macOS | Compares a question with every stored vector in one operation |
| Main on-device model | `gemma4:12b`, 12.4 billion parameters, 7.7 GB | The model the engine was fitted and tested on |
| Small on-device model | `qwen3.5:4b`, 4.5 billion parameters, 4.0 GB | Shows whether a smaller model uses the same memory as well |
| Embedding model | `qwen3-embedding:0.6b`, 639 MB | Turns text into vectors for search by meaning |
| Cloud model | Claude (`claude-sonnet-5-5`) through the Anthropic API | The ceiling the gap is measured against |
| Chroma | 1.5.9 | The vector database baseline |
| LangChain | langchain-core 0.3.86 | Shows Burrow working as a retriever inside a framework |
| Python | 3.9.6 | The evaluation harness and the charts |
| Generation settings | Temperature 0, seed 7, at most 2,048 tokens written | Repeatable local answers; the cloud model does not accept a temperature |

### 5.2.3 Deployment and Reproducibility

Burrow is installed by building it from source. The steps are in the README and Appendix 4.

i) Install Xcode and Ollama, then pull the two local models and the embedding model with `ollama pull`.
ii) Build the engine with `swift build -c release` and the app with `app/build.sh`.
iii) Run `swift test`. The expected result is 212 passing tests.
iv) Index a folder with `burrow index`, measure a model with `burrow fit`, add the starter skills with `burrow skills --install`, and ask with `burrow ask --mode engine`.

## 5.3 System Implementation

The engine is one Swift library, `BurrowCore`, with four thin surfaces over it: a command-line tool, a native Mac app, a terminal chat, and a Model Context Protocol server. Table 5.3 lists the parts and the requirement each one meets.

!tab Table 5.3: Implemented parts of the engine
!widths 1.4,3.6,1.3
| Part | What it does | Requirements |
| `Vault`, `Scanner`, `Chunker` | Reads the vault, cuts files into pieces, and re-reads only what changed | FR-01 |
| `Retrieval`, `Index` | Ranks pieces by words and meaning, merges the rankings, follows links | FR-02, FR-03 |
| `Engine.brief` | Decides whether the vault is needed, how to read it, and which skill fits | FR-04, FR-05, FR-10 |
| `Fit` | Measures a model once and sets how much it is shown | FR-06 |
| `Engine.engage` | Has the model answer, checks its citations, retries once | FR-07, FR-08 |
| `Engine.lessons`, `keep` | Proposes notes from a conversation and writes the accepted ones | FR-09 |
| `Skills` | Stores methods as Markdown files in the vault | FR-05 |
| `BurrowMCP`, `BurrowTools` | Gives the same memory to outside models and tools | FR-10 |

### 5.3.1 The Engine at Work

Figure 5.1 shows one question in the Mac app. Under the answer the app states what the engine decided, the method it handed to the model, and the files it read. Each file opens at the cited line.

!fig figures/screens2/app-ask.png | Figure 5.1: A question answered in the Mac app, with the engine's decision, the method used and the files read. | 6.2

Figure 5.2 shows the same engine in the terminal. The lines after the answer are the engine's own account: the decision and its reason, the skill, the files read, how many cited places were checked, and the time spent before the model was called.

!fig figures/screens2/terminal-engine.png | Figure 5.2: The engine answering in the terminal and reporting what it decided, read and checked. | 6.2

The decision is made in `Engine.brief`. The extract below is the part that reads the signal from one cheap search and chooses a route.

!code
let nearest = found.signal.nearest
if found.excerpts.isEmpty {
    route = Route(mode: .none, why: "the vault has nothing on this")
} else if let nearest, nearest < settings.memoryFloor {
    route = Route(mode: .none, why: "nothing in the vault is close to this")
} else if let nearest, nearest < settings.looseMatch, let matched,
          !matched.skill.needsVault, matched.closeness > nearest {
    route = Route(mode: .none, why: "this is a task to work out, not something to look up")
} else {
    let first = found.paths.prefix(4)
    let code = first.filter(Engine.isCode).count
    if code * 2 >= first.count, code > 0 {
        route = Route(mode: .walk, why: "the closest files are code, so their links are followed")
        found = try await retrieve(question, mode: .walk, budget: budget, embedder: embedder, scope: scope)
    } else {
        route = Route(mode: .search, why: "the closest files are notes and documents")
    }
}
!endcode

Search by meaning compares the question with every stored vector. The vectors are kept as one block of unit rows in a file mapped into memory, so the comparison is a single matrix multiplication and opening a vault costs nothing until a row is read.

!code
func nearest(to query: [Float], limit: Int) -> [Int] {
    var scores = [Float](repeating: 0, count: ids.count)
    storage.withUnsafeBytes { raw in
        let rows = (raw.baseAddress! + offset).assumingMemoryBound(to: Float.self)
        vDSP_mmul(rows, 1, query, 1, &scores, 1, vDSP_Length(ids.count), 1, vDSP_Length(dimension))
    }
    ...
}
!endcode

A skill is a plain Markdown file in the vault's `Skills` folder. Figure 5.3 shows one. The line beginning `when:` is what a question is matched against, and the numbered steps are what the model is given.

!fig figures/screens2/skill.png | Figure 5.3: A skill as it is stored in the vault: a method the engine hands to the model for one kind of task. | 5.6

### 5.3.2 The Engine Serving Other Models and Tools

The engine is not tied to the model it hosts. `burrow brief` and the MCP tool `vault_prepare` return the same decision, skill and excerpts as text, for any model to use. Figure 5.4 shows a cloud coding assistant calling `vault_prepare` through MCP, and Figure 5.5 shows Burrow used as the retriever inside a LangChain pipeline in place of a vector database.

!fig figures/screens2/mcp.png | Figure 5.4: An outside model asking Burrow to prepare a task through the Model Context Protocol. | 6.2

!fig figures/screens2/langchain.png | Figure 5.5: Burrow as the retriever in a LangChain pipeline. | 6.2

### 5.3.3 Data Used

Table 5.4 lists the material in the evaluation vault and the questions asked of it. The documents are real and were fetched from their official sources on 10 November 2026. The private project is Burrow's own source and decision log at an earlier tag, which no model can have seen. The questions were written by a language model from the documents and checked by a script: every answer key had to appear in the quoted evidence, and no key could appear in its own question.

!tab Table 5.4: The evaluation vault and its questions
!widths 1.3,2.6,0.8,0.8,0.8
| Subject | Material | Files | One-fact questions | Several-fact questions |
| Kenyan law | Data Protection Act (Cap. 411C) and its three sets of 2021 regulations, from Kenya Law | 23 | 25 | 15 |
| 2026 software | SQLite, Python 3.15, Ollama and Model Context Protocol release notes dated 2026 | 25 | 25 | 15 |
| Private project | Burrow's source and decision log at tag `evaluation-1` | 39 | 25 | 15 |
| Reasoning | 50 problems from the GSM8K test split (Cobbe et al., 2021), chosen with a fixed seed | - | 50 | - |

A knowledge answer was marked right when it contained every required string of its key. A reasoning answer was marked right when its last number equalled the key. Table 5.5 shows one question of each kind.

!include generated2/examples.md

## 5.4 Testing

### 5.4.1 Test Strategy

Three levels of test were used. Unit tests check each part of the engine with stand-in models, so they are exact and repeatable. A fixture of six notes and six questions checks every set-up of the harness from end to end. The experiments in Section 5.5 then measure the engine on tasks it was not developed on. The engine was frozen before the experiments: its binary is identified by a SHA-256 hash that is written into every results folder.

### 5.4.2 Test Cases and Results

All 212 automated tests passed on the frozen source. Table 5.6 gives one test case per requirement, and Appendix 5 lists every test.

!tab Table 5.6: Test cases by requirement
!widths 0.6,0.7,1.9,1.7,1.5
| Case | Requirement | Input | Expected | Actual |
| TC-01 | FR-01 | A project indexed twice with nothing changed, then with one file changed and one removed | Nothing rebuilt the second time; the old words gone the third time | Pass |
| TC-02 | FR-02 | A question whose words are absent from the right file | The file is found by meaning | Pass |
| TC-03 | FR-02 | 300 random vectors and a random question | The same order as comparing every vector by hand | Pass |
| TC-04 | FR-03 | A question that names only the first of three linked files | The third file is reached by the walk and not by search | Pass |
| TC-05 | FR-04 | A question the vault knows nothing about | The vault is left out and the model gets only the question | Pass |
| TC-06 | FR-04 | A question whose closest files are code | Links are followed | Pass |
| TC-07 | FR-05 | A sum, with a calculation skill and a documents skill in the vault | The calculation skill and no excerpts | Pass |
| TC-08 | FR-05 | A file in the `Skills` folder that matches the question's words | Never returned as an excerpt | Pass |
| TC-09 | FR-06 | A fast small model, a fast large model, a slow large model | 8,000, 24,000 and 6,400 characters | Pass |
| TC-10 | FR-06 | A model that accepts only 4,096 tokens | The budget fits inside the window | Pass |
| TC-11 | FR-07 | Any question with memory | The rules tell the model that excerpts are data | Pass |
| TC-12 | FR-08 | An answer citing a file it was not shown, then a grounded second answer | One retry; the second answer kept | Pass |
| TC-13 | FR-08 | A second answer that cites more unseen places than the first | The first answer kept | Pass |
| TC-14 | FR-09 | Three proposed notes, one quoting words the person never typed | Only the two backed by the person's words kept | Pass |
| TC-15 | FR-09 | The same decision stated in two conversations | Written once | Pass |
| TC-16 | FR-10 | `vault_prepare` called through the tools and through MCP | The decision and the excerpts, no chat model called | Pass |
| TC-17 | NFR-02 | The index deleted and rebuilt | No note lost | Pass |
| TC-18 | NFR-03 | An excerpt containing text that tries to close its own block | The block cannot be closed from inside (tools path) | Pass |
| TC-19 | NFR-04 | Every answer in Section 5.5 | Tokens and seconds recorded | Pass |
| TC-20 | NFR-06 | `swift test` on the frozen source | 212 tests pass | Pass |

### 5.4.3 Defects Found

Table 5.7 lists the faults found while building and testing the engine. Those found after the freeze were left unfixed, so that the measured engine is the one described.

!tab Table 5.7: Defects found
!widths 0.6,2.6,1.6,1.4
| No. | Fault | How it was found | State |
| D-1 | A small model opened factual answers with "The reason is not recorded." | Development questions | Fixed before the freeze: the rule on reasons is given only when why is asked |
| D-2 | Two of six fixture answers were a bare citation with no sentence | Harness fixture | Fixed before the freeze: the rules ask for a sentence first |
| D-3 | The first fit measured on prose and overflowed an 8,192-token window on code | Gemma 4 12B on a code question | Fixed before the freeze: the fit measures on prose and code |
| D-4 | A skill for comparing options was handed to a plain lookup | 26 labelled development questions | Fixed before the freeze: thresholds raised |
| D-5 | The harness cut cloud answers at 600 tokens, leaving 8 of 35 empty | First cloud run | Harness corrected; the run was set aside and repeated |
| D-6 | The engine's own prompt does not stop an excerpt from closing its block, though the tools path does | Review of the frozen source | Open |
| D-7 | The check and retry run only for `burrow ask`; the app shows unverified citations without asking again, and the terminal chat does not check | Review of the frozen source | Open |
| D-8 | `vault_prepare` uses a fixed budget, not the fitted one | Review of the frozen source | Open |
| D-9 | An empty question is sent to the model, and a missing folder is treated as an empty vault | Carried from the earlier evaluation | Open |

