# Discussion, Conclusions, Recommendations and Future Works {#conclusions}

## Introduction

Small language models that run privately on a laptop know far less than large cloud models, and they forget whatever falls outside their context window. This study built CAMR, an external memory engine that sits beside a frozen model on an Apple-silicon Mac and keeps the model's own notes, its keys and values, in rooms on the SSD. It measured what CAMR closes, what it does not, and at what cost, against the same models without memory and against Claude Haiku, Sonnet and Opus 5.5 reading as much of the history as their windows hold. This chapter answers each objective of Section {sec:specific-objectives} with the evidence of Chapter 5 (Section {sec:conclusions-obj}), states the limitations of that evidence (Section {sec:limits-6}), and sets out what should be done because of it (Section {sec:recommendations}) and what remains open (Section {sec:future}). It adds no new results; every statement refers to the section of Chapter 5 that supports it.

## Conclusions by Objective {#conclusions-obj}

### Objective i: Techniques and Their Limits on a Device

Selective techniques that keep what the model reads small work for a small model; techniques that give it more text do not. In the baseline, entity bridging, a one-step hop that needs no graph, doubled full-support recall on 2WikiMultiHopQA (35.8% to 78.4%) at the same budget, while recency and importance weighting lowered it (Section {sec:baseline-results}). In the engine, a desk of one room plus four moments knew 158 facts on the development lives, against 144 for three rooms read as words, and larger rooms knew fewer facts at every setting tried (Section {sec:rooms-results}). The reuse of a model's own keys and values worked within one room, where notes answered as the words did (164 against 163 facts), but notes written separately did not combine for a small reader: 2 of 46 facts against 32 from the words (E-15). This limit is the one that the literature on cache blending works around (Yao et al., 2025), and it is why the engine reads one room per question. A long context window is not a substitute for memory: Claude's one-million-token window held only the newest days of a 3 or 4 million-token history, and it recalled nothing planted there (Section {sec:past-window}).

### Objective ii: The Design

The design kept what it is told as the model's own notes, found what a question needs by one similarity search over every moment, and controlled what the model reads by a fixed desk of one room of at most 512 tokens plus four moments re-read as words. Three further layers made the memory usable as it grows: tiers that keep hot rooms in RAM and put weak rooms to sleep within a disk budget, a vault of linked plain-text notes that a person can read and edit, and reach, which decides whose memory a question reads (Chapter 4). The design was faithful where it was tested strictly: within one room, notes and words gave the same answer to 3,483 of 3,600 questions (Section {sec:rooms-results}). It has one structural limit: a question sees one room, so facts told in two places were almost never joined (0 of 10 two-hop questions at 2M for the 4B; Section {sec:families}). Of the four reaches, project memory was best (26 of 40), and mixing in a second project cost 2 answers (Section {sec:reach-results}).

### Objective iii: On the Device

CAMR ran entirely on a MacBook Pro M5 Pro with no dedicated graphics card, with the model and its memory on the Mac, and as a native Mac app with Chat and Code (Section {sec:app-impl}). The memory grew on the SSD without making the model slower or heavier: from 112 thousand to 2.01 million tokens of history, the 1.7B's first word stayed at 0.08 to 0.15 s, retrieval at 17 to 24 ms and RAM at about 4.3 GB, while sleep held the room files at their 40 GB budget (Section {sec:speed-results}). After the graphics buffer cache was capped, the 4B's whole process needed 5.4 to 7.5 GB at 3 and 4 million tokens, against 15.2 GB for the same model reading only its newest 64,000 tokens (Section {sec:ram-results}). Two marks set for the device were met and one was not: the first word at 2,000 words came in 0.233 s, under the 0.5 s mark, but notes were 4.6 times sooner than words, not the 10 times required, because the mark was estimated on a slower machine (Section {sec:rooms-results}). The proposal's embedded database was replaced by files on the SSD (Table {tab:changes}), and the cost of memory moved to storage: about 40 GB for 2 million tokens before sleep.

### Objective iv: Evaluation of the Gap

Within its window, the cloud model is better; beyond it, memory is. Up to 1M tokens, Claude Sonnet alone answered 28 to 43 questions per checkpoint against 25 to 26 for the 4B with CAMR. At 2M, the 4B with CAMR answered 29 of 73 against Sonnet's 32 and Opus's 31, nearly closing the gap; at 3M and 4M it answered 29 both times, while Sonnet fell to 13 and then 10 (Sections {sec:haul-results} and {sec:past-window}). Against the same model without memory the gain was large at every size of history past the window: 29 against 11 for the 4B at 2M, and 27 against 11 for the 8B. CAMR's first word came in 0.2 to 0.3 s, against 13 to 105 s for Sonnet and Opus (Section {sec:yardstick}).

The engine helps knowledge-bound tasks and not reasoning-bound ones, as the proposal predicted. At 2M it led Claude on facts planted far back (6 against 4 of 10) and on code that had to use the project's own helpers (4 against 2), but trailed on changed facts, look-alikes and corrected mathematics, where several moments must be weighed against each other, and no model built the page that needed a design from week 1 and a change from day 61 (Section {sec:families}). The baseline found the same on public benchmarks: with memory, 20 of 22 small models matched the cloud model on long-tail facts, while memory left an 83-point gap on arithmetic (Section {sec:baseline-results}). The 4B with CAMR was also honest: it declined 9 of 10 never-said questions at 2M and all 10 beyond it.

### Objective v: How Much to Read, and What Each Part Contributes

For a small reader, the best desk is small and fixed: one room of at most 512 tokens and four moments re-read (Section {sec:rooms-results}), which keeps the context at a few hundred tokens however large the memory grows. The comparisons isolated what each part contributes. Saving notes rather than words bought speed, not accuracy: the same 1.7B answered 14 to 20 with notes and 16 to 17 with the same memory as words, three times sooner, at 40 GB of disk against 0.1 GB (Section {sec:notes-words}). A larger reader did not raise the ceiling: the 8B and the 27B answered 27 at 2M against the 4B's 29 (Section {sec:bigger}). The instructions mattered more than the memory for the smallest model: the 1.7B's own wording raised its score from 15 to 21 at 2M but cut its honest declines from 7 to 3 (Section {sec:wording}). The buffer-cache cap cut the process's RAM by more than half and nearly doubled its reading speed, with identical answers (Section {sec:ram-results}). Project reach was the right default (Section {sec:reach-results}).

Table {tab:alignment} summarises how each objective was answered.

Table: {#alignment} Alignment from objectives to evidence and conclusions

| Objective (Section {sec:specific-objectives}) | Evidence (Chapter 5) | Conclusion | Status |
|---|---|---|---|
| i. Investigate techniques and their limits | {sec:baseline-results}, {sec:rooms-results}, {sec:past-window} | Selective, small desks work; separately written notes do not combine; a long window forgets the start | Met |
| ii. Design a lightweight memory engine | Chapter 4; {sec:rooms-results}, {sec:reach-results} | One room of the model's own notes plus four moments, with tiers, a vault and reach; faithful within a room | Met, with one structural limit (one room per question) |
| iii. Implement it on a consumer laptop | {sec:app-impl}, {sec:speed-results}, {sec:ram-results} | Runs on the Mac, flat in time and RAM as memory grows; 5.4–7.5 GB at 3–4M tokens | Met; NFR-02 (10×) not met; files replace the database |
| iv. Evaluate the gap by task type | {sec:haul-results}, {sec:past-window}, {sec:families}, {sec:yardstick} | Nearly level with Sonnet at 2M, ahead past its window; knowledge closed, reasoning not | Met on a scripted test |
| v. Determine how much to read and what each part adds | {sec:rooms-results}, {sec:notes-words}, {sec:bigger}, {sec:wording}, {sec:reach-results} | A small fixed desk; notes buy speed; the memory sets the ceiling; wording matters for the 1.7B; project reach | Met |

### Contribution

The study contributes:

1. An open memory engine that keeps a frozen model's own keys and values in rooms on the SSD, with a core in RAM, tiers and sleep under fixed budgets, a vault a person can read and reach, whose wait and RAM stayed flat as memory grew to 2 million tokens.
2. The Long Haul, a scripted project of 2 to 4 million tokens with 216 questions graded by rule, in eight families that each isolate one way of failing, and a harness in which every answer records what it cost and every number names the code that made it.
3. A measured comparison of a 1.7B to 27B local model with memory against Claude Haiku, Sonnet and Opus alone, past their window, with time, RAM and dollars per answer.
4. A native Mac application with Chat and Code that shows the engine at work, drawing only what the engine measures, and a pairing that gives Ollama and other local servers memory as words.
5. The baseline's findings on public benchmarks: on facts, memory lets a small model match a cloud model; on reasoning, it does not.

## Limitations of the Evidence {#limits-6}

The conclusions above hold within limits that the evidence itself sets.

1. **The benchmark is scripted.** The Long Haul is one invented project, fixed by its seed and built to be hard in known ways. It tests the mechanism fairly, every contender on identical questions, but it is not a sample of real work, and it does not show how CAMR would serve a real user.
2. **Claude is a yardstick, not an opponent.** Claude answered alone, with no memory, from the newest part of the history that fits its window. A cloud service with a memory of its own would do better past its window. The comparison shows what a window alone does, not the best a cloud provider could build, and it was run once per model with the provider's service of that night.
3. **The RAM figures before the cap are understated.** Runs before the buffer-cache cap (the 1.7B and the 4B up to 2M) report MLX's peak, not the process's footprint, which reached 19.2 GB on the 4B (E-40). Their scores are unaffected, and every later record logs the footprint.
4. **The samples are small and single.** Each checkpoint asks 34 to 73 questions, 10 per family; differences of one or two answers, including the 3-answer gap at 2M, are within noise. No run was repeated for variance, apart from the 4B's 3M checkpoint, which gave identical verdicts.
5. **What was not measured.** The engine's own contenders were not run on the public suites; LongMemEval and two further suites have loaders but no runs; the Code agent, the core and waking an asleep room have no benchmark; the app had no user study and no accessibility audit; and every number comes from one Mac. [[MEDIA-LIMIT]]

## Recommendations {#recommendations}

Each recommendation follows from a result or limitation in Chapter 5; essential safeguards come first (Table {tab:recs}).

Table: {#recs} Recommendations

| Priority | Audience | Recommended action | Evidence and condition |
|---|---|---|---|
| 1. Essential | Anyone measuring memory on Apple silicon | Cap MLX's buffer cache and record the process's footprint, not only MLX's peak | 19.2 GB footprint against 5.7 GB reported, then 7.5 GB with the cap and identical answers (Section {sec:ram-results}) |
| 2. Essential | Anyone letting a small model act from memory | Use a reader that declines what it was never told (here the 4B), and confirm every tool call | The 1.7B made up 42 of 45 never-told errands; the 4B declined 9 to 10 of 10 never-said questions (Sections {sec:rooms-results}, {sec:families}) |
| 3. High | Developers of on-device assistants | Keep a growing memory outside the context window, as the model's notes in rooms on the SSD, and read one small room per question | First word and RAM flat from 112K to 2.01M tokens; 29 of 73 at 2, 3 and 4M (Sections {sec:speed-results}, {sec:past-window}) |
| 4. High | The same | Prefer a 4B reader on a 24 GB Mac: an 8B or a 27B with the same memory did not answer more, and cost time and RAM | Section {sec:bigger} |
| 5. High | Users and app builders | Keep one memory per project, not per conversation or for everything | Project 26 of 40; session 11; global 24 (Section {sec:reach-results}) |
| 6. Medium | Builders of memory engines | Fix the model's instructions before any test run and report a small model under more than one wording | The 1.7B scored 15 or 21 at 2M by wording alone (Section {sec:wording}) |
| 7. Medium | Researchers evaluating memory | Test past the cloud model's window, count declines on never-said questions apart from facts known, and log the cost of every answer | Sections {sec:past-window}, {sec:yardstick} |
| 8. Lower | The student and supervisor | Obtain ethics approval before any study with real users, and rotate the API key used for the yardstick | Section {sec:ethics} |

## Future Works {#future}

Each direction extends CAMR from a limitation in Chapter 5, ordered by expected value (Table {tab:future}).

Table: {#future} Prioritised future works

| Priority | Direction and rationale | How to evaluate |
|---|---|---|
| 1 | **Several rooms read together.** One room per question joined 0 of 10 two-hop questions at 2M; notes written apart do not combine for a small reader. Re-encoding where rooms meet, in the manner of cache blending, could join them | The two-hop and changed-fact families, at a first word no higher than one room's |
| 2 | **Sleep that distils.** Notes are about 29,000 times their text, and sleep now only puts rooms away as words. Naps on the charger that distil what was learnt, checked by a quiz before it is kept, would shrink the memory | Disk per million tokens and Long Haul scores before and after a night's sleep |
| 3 | **Settling unsure facts at recall.** The smallest reader guessed when it did not know, and changed facts were often answered with an old value. A check before answering could resolve the doubt from the moments or ask the user | Never-said declines and stale answers on the Long Haul, with facts known not falling |
| 4 | **The engine on the public suites and LongMemEval.** The suites ran on Claude and Ollama only; LongMemEval has a loader and a judge but no run | Suite accuracy with the engine's own wording, LongMemEval by question type |
| 5 | **The native engine behind the pairing.** Through Ollama and the OpenAI-compatible endpoint, memory goes in as words | First word and accuracy through the endpoint, as notes against words |
| 6 | **Other Macs and real users.** One M5 Pro was measured; 8 GB Macs and older chips were not. No user has used the app over weeks | The Long Haul on two more Macs; with ethics approval, a study of the app over several weeks |
| 7 | **The page that grows.** No model, Claude included, built the page that needed a design from week 1 and a change from day 61 | The three page probes, checked in a headless browser |

## Closing Remarks

The study set out to measure how much of the gap between an on-device and a cloud language model a lightweight memory engine bridges. On a long scripted project, the answer is: nearly all of it at 2 million tokens, all of it and more once the history outgrows the cloud model's window, and none of it on reasoning that memory cannot supply. A 4-billion-parameter model on a laptop, given its own notes back from the SSD, answered as many questions at 4 million tokens as at 2 million, in a third of a second and a process of 5 to 8 GB. What a window forgets, a memory outside it keeps.
