!tab Table A2.2: Changes to Chapters 1 to 3 since the approved proposal
!widths 0.9,2.9,2.4
| Section | What changed | Why |
| Whole document | The engine is named Burrow. The old name appears once, in 3.3. | The engine was rebuilt and renamed after the Sprint II review of 5 November 2026. Title and topic are unchanged. |
| Acknowledgment | "this proposal" became "this project"; thanks to the Sprint II panel added. | Final report. |
| Abstract | Rewritten second paragraph: vault, five engine steps, Swift, app, terminal chat and MCP server, the conditions compared. One results sentence left pending. | Aligned with what was built. |
| Keywords | "prompt compression" replaced by "token budget". | The engine budgets what is read; it does not compress prompts. |
| Abbreviations | Removed CAMR and ANN. Added BM25, FTS5, GSM8K, MCP, RRF, SWE-bench. | Terms used in the revised text. |
| 1.1 | "typically between one and three billion parameters" removed from the definition of small models; one sentence added on Gemma 4 and Qwen3.5. | The models hosted are 12 and 4 billion parameters. |
| 1.2, last paragraph | Solution paragraph describes the vault, the decision whether to use it, the fitted token budget, and notes written with consent. "Screened notes from past interactions" removed. | The memory as built is the person's own files, not only notes from interactions. |
| 1.3.2 (ii) | Retrieval policy "ranks notes by similarity, recency, and importance" became "ranks stored passages by word match and by meaning and follows the links between files". | Retrieval as built is BM25 and cosine merged by reciprocal rank fusion, then a walk over links. |
| 1.3.2 (iii) | "in Swift on an Apple-silicon consumer laptop", "index of the memory store". | Implementation language and platform as built; the database is a rebuildable index beside the vault. |
| 1.4 | No change. | Approved wording kept. |
| 1.6 | Laptop is a MacBook Pro M5 Pro with 24 GB (was 16 GB). Models named: Gemma 4 12B, Qwen3.5 4B, Claude. Public QA benchmarks replaced by three curated subjects plus GSM8K. Scope sentence now includes the command-line tool, Mac app, terminal chat and MCP server. | As built; surfaces added after the Sprint II review. |
| 1.7.1 | Third limitation now says the curated questions were written by a language model. | Honest statement of the evaluation as run. |
| 1.7.2 | "repeated timing runs and median latencies" became "seconds taken by every answer". "Several established benchmarks" became "three unrelated subjects and one public benchmark". The optional graph layer is reported as built in a light form. | The plan was one run per question; link walking was built. |
| 2.1 | One clause added: systems Burrow is compared with or built to work beside. | Three related works added. |
| 2.2.1 | One sentence added on Gemma 4 and Qwen3.5. | Models hosted in the study. |
| 2.2.4 | "Memory should be stored densely, as short structured notes" became "what the model reads should be dense, short excerpts and short notes". | The vault keeps the person's files whole; density is applied to what is read. |
| 2.2.5 | Engine "mirrors in its index, its retrieval, and its token budgeting". Security design choices became: notes backed by the person's own words, nothing written without consent. LongMemEval cited as 2025 (its conference year). | Provenance and screening were realised as evidence and consent in the Learn step. |
| 2.3 | Heading comma corrected ("Memory, Retrieval, and Compression Techniques"). | Typing error in the proposal. |
| 2.3.3 | Three sentences added on BM25, embedding comparison and reciprocal rank fusion. | Techniques the engine uses, not reviewed in the proposal. |
| 2.4.2 | "Adopted directly by this study's retrieval policy" became "shaped the retrieval policy first proposed". | Recency and importance scoring are not in the engine as built. |
| 2.4.4 | Last clause: Burrow follows existing links instead of building a graph with a language model. | The associative layer was built as link walking. |
| 2.4.6 to 2.4.8 | New: Chroma, Obsidian, Claude Code with the Model Context Protocol, each with one figure from its official source. | The baseline, the form of the memory, and the cloud assistant Burrow works beside. |
| Figures 2.1 to 2.5 | Same images; a source added to each caption. | Course guide: cite figure sources. |
| Table 2.1 | Three rows added. | Three related works added. |
| 2.5 | One sentence added to the first paragraph; "against both a plain vector database and a cloud model" added to the second; "milliseconds" became "seconds". | New related works; times are reported in seconds. |
| 2.6 and Figure 2.9 | Independent variable now names the Decide, Fit, Check and Learn steps and the skills. Figure redrawn (was Figure 2.6). | The proposal's figure carried the old name and the old pipeline. |
| 3.1 | One sentence added: departures from the proposal are stated. | Course guide: Chapters 1 to 3 aligned with what was built. |
| 3.2.1 | PopQA, HotpotQA and 2WikiMultiHopQA replaced by three curated subjects (Kenyan data protection law; software documentation of 2026; a private project). GSM8K kept. | The memory is a personal vault; an encyclopaedia corpus does not represent it. |
| 3.2.2 | Sample described: 25 single-fact and 15 multi-fact questions per subject, 50 GSM8K questions by fixed seed; keys checked by script; subjects act as distractors for one another. | As run. |
| 3.2.3 | Three conditions became four, with a Chroma baseline. | As run. |
| 3.2.4 | Benchmark metrics became accuracy by answer key; bootstrap intervals became an exact sign test; frozen engine added. | As run. |
| 3.3 and Figure 3.1 | Four increments plus one optional became five. Increment 3 lists the engine steps. Increment 5 is the app, terminal chat and MCP server. Sentence on the Python prototype and the Swift rebuild. Figure redrawn. | As built. |
| 3.4 | Requirements restated for vault, index, Decide, link following, fitted budget, Check, consent. "Single command" became "from the command line". | As built. |
| 3.5.1 | Write path, store, read path became vault, index, and the five engine steps; mapping to the proposal's three mechanisms stated; skills added. | As built. |
| 3.5.2 | Fourth condition (cloud model with Burrow), plain-search control and Chroma baseline added; rules for an undefined gap and for the private project; engine freeze and written plan added as a second guard. Equation 3.1 kept. | As run. |
| 3.5.3 | Task types drawn from curated subjects; paragraph added on the two earlier tests (101 SWE-bench bug fixes, simulated developer agents). | As run. |
| 3.5.4 | Exact match and F1 became answer-key accuracy; peak memory and on-disk size removed from the reported measures; sign test named. | As run. |
| 3.5.5 | Ablation described as: plain search control, full engine, engine without skills, engine without Check. Pending note on a token budget sweep. | The written plan lists only these ablations. |
| 3.5.6 | Threat list updated: temperature zero, sign test, frozen engine and separate development questions, tested marking rules. Manual audit of graded answers removed. Two remaining threats stated. | As run. |
| 3.6 | Tools are now Swift, SQLite with FTS5, Ollama with Gemma 4 and Qwen3.5, Anthropic API, Qwen3 Embedding, Chroma, LangChain, Python (harness only), Git. | As built. |
| 3.7 | Deliverable added: application, terminal chat and MCP server. Engine is a Swift package with a command-line tool. | As built. |
| References | Rebuilt to APA 7 with full author lists and DOIs. Corrected: AgentPoison (five authors, title ends "knowledge bases"), the memory injection paper (Dong and seven co-authors, correct title), Peffers et al. (volume, issue, pages). Added: Anthropic, Chroma, Cormack, Data Protection Act, Gemma 4, Jimenez, LangChain, Model Context Protocol, Obsidian, Ollama, Qwen3.5, Robertson, SQLite, Zhang (Qwen3 Embedding). | APA 7; new sources. |
