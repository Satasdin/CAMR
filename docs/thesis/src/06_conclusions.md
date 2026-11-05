# Conclusions, Recommendations and Future Works {#conclusions}

## Introduction

This chapter closes the chain from the problem and objectives of Chapter 1 to the implemented system and the evidence of Chapter 5. Section {sec:conclusions-obj} states what the study established, objective by objective, with its contribution and the conditions within which the conclusions hold. Section {sec:recommendations} sets out what should be done on the basis of the findings, and Section {sec:future} the work that remains. The chapter introduces no new experiments, results or citations: every statement rests on evidence, a limitation or an open question already reported in Chapter 5.

## Conclusions {#conclusions-obj}

Small language models that run privately on a laptop know far less than large cloud models, and they forget whatever falls outside their context window. This study set out to measure how much of that capability gap a lightweight external memory engine bridges, by task type and at what cost. It built CAMR, which sits beside a frozen model on an Apple-silicon Mac and keeps the model's own notes, its keys and values, in rooms on the SSD, together with a native Mac application with Chat and Code. It evaluated CAMR against the same models without memory and against Claude Haiku, Sonnet and Opus 5.5 reading as much of the history as their windows hold. The conclusions follow the order of the specific objectives (Section {sec:specific-objectives}).

### Objective i: Techniques and Their Limits on a Device

On a small on-device model, memory techniques that keep what the model reads small and related work, and techniques that give it more or less related text do not. Entity bridging found the second hop of a question without a graph, while weighting by recency and importance hurt; saved caches were usable as whole rooms but not when written separately and combined; and a long context window did not substitute for memory once the history outgrew it (Section {sec:disc-obj1}).

### Objective ii: The Design

The design of one room of the model's own notes plus the four closest moments, with tiers, sleep, a vault, reach and an assistant around it, keeps and finds memory faithfully: within a room, notes knew as many facts as the words they came from, meeting the requirement set before the test. It serves chat, files, code and evaluation through one read path. Its structural limit is that a question sees one room, so facts told in two places were almost never joined (Section {sec:disc-obj2}).

### Objective iii: On the Device

The engine and its application run entirely on one consumer Mac, and the memory can grow on the SSD without making the model slower or heavier: the wait for the first word and the RAM stayed flat as the history grew from 112 thousand to 2 million tokens, and the 4B's whole process needed 5 to 8 GB after the graphics buffer cache was capped. Five of the six device requirements were met; notes were 4.6 times sooner than words rather than the 10 times required. The cost of memory moved to storage, which sleep and 8-bit rooms keep within a budget (Section {sec:disc-obj3}).

### Objective iv: Evaluation of the Gap

Within its window the cloud model was better; beyond it, memory was. At 2 million tokens a 4B model with CAMR answered 29 of 73 questions against 32 for Claude Sonnet alone, and at 3 and 4 million it still answered 29 while Sonnet fell to 13 and 10, with a first word in a third of a second instead of 13 to 105 seconds. Memory closed knowledge-bound gaps (facts told long ago, code that must use the project's own helpers, facts kept from files) and not reasoning-bound ones (joining facts, weighing changed values, building on a design over weeks). The 4B was also honest about what it had never been told (Section {sec:disc-obj4}). Against conventional retrieval-augmented generation over the same memory, CAMR answered as many questions, two to four times sooner and with errands done three times as often; against pasting the history into a long context, it knew more and stayed fast as the history grew (Section {sec:disc-rag}).

### Objective v: How Much to Read, and What Each Part Contributes

A small reader should read a small, fixed desk: one room of at most 512 tokens and four moments. The memory's organisation into dated rooms chosen by similarity carried the answers; the saved notes bought speed rather than accuracy; a larger reader did not raise the ceiling; project memory was the best reach; 8-bit rooms kept every answer; and the smallest model's wording mattered more than its memory (Section {sec:disc-obj5}).

Table {tab:alignment} summarises how each objective was answered.

Table: {#alignment} Alignment from objectives to evidence and conclusions

| Objective | Evidence (Chapter 5) | Conclusion | Status |
|---|---|---|---|
| i. Investigate techniques and their limits | {sec:disc-obj1} | Selective, small desks work; separately written notes do not combine; a long window forgets the start | Met |
| ii. Design a lightweight memory engine | {sec:disc-obj2} | One room of the model's own notes plus four moments, with tiers, a vault, reach and an assistant; faithful within a room | Met, with one structural limit (one room per question) |
| iii. Implement it on a consumer laptop | {sec:disc-obj3} | Runs on the Mac, flat in time and RAM as memory grows; 5 to 8 GB at 3 to 4 million tokens | Met, except NFR-02 (10 times sooner) |
| iv. Evaluate the gap by task type | {sec:disc-obj4} | Nearly level with Sonnet at 2 million tokens, ahead past its window; knowledge closed, reasoning not | Met on a scripted test |
| v. Determine how much to read and what each part adds | {sec:disc-obj5} | A small fixed desk; notes buy speed; the memory sets the ceiling; project reach; 8-bit rooms | Met |

### Contribution

The study contributes:

1. An open memory engine that keeps a frozen model's own keys and values in rooms on the SSD, with a core in RAM, tiers and sleep under fixed budgets, a vault a person can read, and reach, whose wait and RAM stayed flat as memory grew to 2 million tokens.
2. The Long Haul, a scripted project of 2 to 4 million tokens with questions graded by rule in eight families that each isolate one way of failing, and a harness in which every answer records what it cost and every number names the code that made it.
3. A measured comparison of 1.7B to 27B local models with memory against Claude Haiku, Sonnet and Opus alone, within and past the cloud model's window, with time, RAM and cost per answer.
4. A native Mac chat application, installed like any other, that routes, researches, reads files, revises its memory and files it on topic shelves, answers code in the conversation, compares CAMR with RAG on any question, and shows the engine's tensors at work; and a pairing that gives Ollama and other local servers memory as words.

### Conditions Within Which the Conclusions Hold

The conclusions hold for one scripted software project, fixed by its seed, with 10 questions per family per checkpoint, so differences of one to three answers are within noise; for the Qwen3 models named, on one MacBook Pro M5 Pro with 24 GB; and for Claude answering alone, without a memory of its own. The application was demonstrated, not evaluated with users. These limits are set out in Section {sec:limitations}. Within them, the study's answer to its question is that a memory outside the window bridges nearly all of the gap on knowledge at 2 million tokens, more than all of it once the history outgrows the cloud model's window, and little of it where the answer must be reasoned across several facts.

## Recommendations {#recommendations}

Each recommendation follows from a result or limitation in Chapter 5 and names its audience. Essential safeguards come first; the others are improvements in order of priority (Table {tab:recs}).

Table: {#recs} Recommendations

| Priority | Audience | Recommended action | Evidence-based reason | Condition |
|---|---|---|---|---|
| 1. Essential | Anyone measuring memory on Apple silicon | Cap MLX's buffer cache and record the process's footprint, not only MLX's peak | The footprint was 19.2 GB while 5.7 GB was reported; the cap gave 7.5 GB with identical answers (Section {sec:ram-results}) | Applies to every long ingest on MLX |
| 2. Essential | Developers letting a small model act from memory | Use a reader that declines what it was never told, and keep every tool call and shell command behind the user's approval | The 1.7B made up 42 of 45 never-told errands; the vision models invented 3 to 5 of 8 never-said answers; the 4B declined 9 to 10 of 10 (Sections {sec:rooms-results}, {sec:media-results}, {sec:families}) | Until a check before answering exists (future work 3) |
| 3. High | Developers of on-device assistants | Keep a growing memory outside the context window, in dated rooms on the SSD, and read one small room per question | The first word and RAM stayed flat from 112 thousand to 2 million tokens, and answers held at 2, 3 and 4 million (Sections {sec:speed-results}, {sec:past-window}) | For knowledge-bound use; not for joining facts |
| 4. High | The same | Prefer a 4B reader on a 24 GB Mac, store rooms at 8 bits and keep a disk budget per shelf | The 8B and 27B did not answer more; 8-bit rooms kept every answer (Sections {sec:bigger}, {sec:bits-results}) | On the Mac tested; other Macs need measuring |
| 5. High | Users and builders of the application | Keep one memory per project, not per conversation or one for everything | Project reach 26 of 40; session 11; global 24 (Section {sec:reach-results}) | Where projects share look-alike names, keep them apart |
| 6. Medium | Builders of memory engines | Fix the model's instructions before any test run, and report a small model under more than one wording | The 1.7B scored 15 or 21 at 2 million tokens by wording alone (Section {sec:wording}) | Small readers especially |
| 7. Medium | Researchers evaluating memory | Test past the cloud model's window, count declines on never-said questions apart from facts known, and log the cost of every answer | Results changed order past the window (Section {sec:past-window}); per-answer cost and wait differed by orders of magnitude (Section {sec:yardstick}) | Any long-history benchmark |
| 8. Lower | The researcher and supervisor | Obtain ethics approval and agree acceptance criteria before any study of the application with real users | No user acceptance or accessibility test was run (Table {tab:testcases}) | Before any claim about real users |

## Future Works {#future}

Each direction extends CAMR from a limitation or open question in Chapter 5, in order of expected value (Table {tab:future}).

Table: {#future} Prioritised future works

| Priority | Direction and rationale | What would change | Data and resources required | How to evaluate |
|---|---|---|---|---|
| 1 | **Several rooms read together.** One room per question joined 0 of 10 two-hop questions at 2 million tokens, and notes written apart do not combine for a small reader | Re-encode where rooms meet, in the manner of cache blending, so that two rooms can share a desk | The Long Haul; the existing harness; the same Mac | Two-hop and changed-fact families, at a first word no higher than one room's |
| 2 | **Sleep that distils.** Notes are about 29,000 times their text, and sleep now only puts rooms away as words | Naps on the charger that distil what was learnt, checked by a quiz before it is kept | The Long Haul cuts; overnight compute on the Mac | Disk per million tokens and Long Haul scores before and after a night's sleep |
| 3 | **Settling unsure facts at recall.** The smallest reader and the vision models guessed when they did not know, and changed facts were often answered with an old value | A check before answering that resolves doubt from the moments or asks the user | The never-said and changed-fact probes | Never-said declines and stale answers, with facts known not falling |
| 4 | **The engine on the public suites and LongMemEval.** The suites ran on Claude and Ollama only; LongMemEval has a loader but no run | The engine's own contenders, with their own wording, on public data | The suites already downloaded; LongMemEval's files and judge | Suite accuracy and LongMemEval by question type |
| 5 | **The native engine behind the pairing.** Through Ollama and the OpenAI-compatible endpoint, memory goes in as words | Notes rather than words behind the endpoint | The pairing's tests; one Ollama-compatible reader in MLX | First word and accuracy through the endpoint, notes against words |
| 6 | **Other Macs and real users.** One M5 Pro was measured, and no user has used the app over weeks | The minimum configuration, and evidence from real use | Two more Macs (8 GB and an older chip); ethics approval and participants | The Long Haul on each Mac; task success and usability in a study of several weeks |
| 7 | **The page that grows.** No model, Claude included, built the page that needed a design from week 1 and a change from day 61 | A Code agent that reads the design and every later change before it writes | The three page probes; a headless browser | The page probes' checks, against the same agent with one room |
