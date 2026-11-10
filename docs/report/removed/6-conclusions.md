# Chapter 6:  Conclusions, Recommendations and Future Works

## 6.1 Introduction

This chapter states what the evidence reported in Chapter 5 supports, what should follow from it and what remains open. It introduces no new results.

## 6.2 Conclusions

The project set out to address two facts: a local model can keep code private but forgets the project between sessions, and much of what matters about a project, such as why a fix was rejected, is not in the code. Burrow was built as a private vault of plain Markdown notes with code folders linked in, read by local models through Ollama.

On the first objective, the review of local model use, the literature in Chapter 2 identified privacy concern as a reason developers hold back from cloud assistants, and the limits of memory in small local models. On the second and third objectives, existing memory systems and code tools were reviewed, and the reasons behind code were identified as the part they treat least.

On the fourth objective, Burrow was designed and implemented as a Mac app, a terminal version and an MCP server over one engine. Fourteen of fifteen functional requirements are verified by passing automated tests, and all 186 tests passed on the frozen version. The graph's pointer interactions await a hand check, and installation has only been shown on the development Mac (RQ1).

On the fifth objective, the evidence divides. Memory did not measurably help simulated developer agents: with the main model, no memory, plain search and link walking passed 5, 5 and 6 of 18 scored held-back sessions, and no session that depended on an earlier decision both passed its task and kept that decision (RQ2). Notes generally reached the model, but it often could not write working code from them. Following links did reach the code that real fixes changed more often than plain search: at least one changed file on 72 of 101 bug fixes against 59 (p = 0.002), and every changed file on 59 against 48 (p = 0.007), with the same amount of reading (RQ3). The index remained 2.3 to 4.4 times the size of the code across four repositories, and median retrieval stayed under a second on 3,833 files, though the longest retrieval took 24 seconds (RQ4).

The contribution of the work is a working private vault in which notes and code are linked and retrieval is checkable, a measured gain from link walking on real repositories under equal reading limits, and a test harness that exposed where the gain stops. These conclusions hold for one Mac, Qwen3 models through Ollama, four Python repositories and synthetic agent tasks. No claim is made about human users.

## 6.3 Recommendations

i) For developers considering Burrow: use it to find the files and recorded decisions relevant to a question, and do not rely on a small local model to carry out changes unsupervised (essential).
ii) For developers using Burrow: check any stated reason against the note it cites, because models continued to mistake a code value for a reason on held-back questions (essential).
iii) For people connecting a cloud assistant through the MCP server: treat excerpts as leaving the Mac, since Burrow's privacy property covers only its own traffic (essential).
iv) For developers of memory tools: include questions whose answer was never recorded, and compare against no memory and plain search under equal reading limits, because a test of correct retrieval alone would have missed the failures reported here (priority).
v) For maintainers of Burrow: correct the misleading message when Ollama refuses a very long question, DEF-08 (priority).

## 6.4 Future Works

- **An admission check after generation.** A prompt rule reduced invented reasons but did not remove them (Section 5.7.2). Verifying each stated reason against a retrieved note, and refusing to state one that cannot be found, would be evaluated on unknown-answer sessions.
- **Larger local models and checked edits.** Most depends sessions failed because the code did not run. Repeating the held-back test with larger local models, and letting an agent run its own code before finishing, would show whether memory helps once the model can write working code.
- **A study with people.** No usability evidence exists. A task-based study with developers on their own projects would measure task completion and trust, and would establish whether the synthetic results carry over.
- **Wider link extraction.** Links are strongest in a few languages. Extending imports to Swift and other languages would be evaluated by the real-repository test of RQ3, broken down by language.
