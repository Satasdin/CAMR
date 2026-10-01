# CAMR: anticipated examiner questions and evidence-backed answers

Preparation notes for the presentation and viva. Each answer points to the evidence in
Chapter 5 (section numbers) and to `docs/FINDINGS.md` (F-numbers), so any number can be
traced to its results file and re-run. Questions are grouped by the order an examiner
usually follows: problem, objectives, design, method, results, cost, validity, product.

---

## A. Problem and objectives (Chapter 1)

**A1. In one sentence, what did you do?**
I built an external memory engine, CAMR, for a frozen small language model running on a CPU. I then measured how much of the gap to a frontier cloud model it closes, on which kinds of task, and at what token and latency cost. Finally I released it as a desktop app.

**A2. Were all five research questions answered?**
Yes. Each is answered in Chapter 6 (section 6.2) with the evidence section it rests on:

| RQ (section 1.4) | Short answer | Evidence |
|---|---|---|
| i. Techniques and their limits on-device | Similarity ranking, gating and entity bridging transfer to small models. Recency/importance weighting (Eq. 4.1) lowered recall on independent questions. | 5.8.1; F1, F1b |
| ii. How much of the gap closes | Single-hop facts: all of it (gap closed 1.00). Multi-hop: half (0.50, CI 0.20–0.90). At n = 200, a 3B model with CAMR (54.0%) matched Kimi K3 closed-book (51.8%). | 5.8.2, 5.8.8; F9, F13 |
| iii. Knowledge vs reasoning | Memory helps knowledge, not reasoning. The residual gap was 10 / 23 / 83 points for facts / multi-hop / maths. | 5.8.2; F8 |
| iv. Best token budget | About 128 tokens for facts and 512 for multi-hop (0.5B). More than that distracts small models. Retrieval recall saturates near 1,024 tokens. | 5.8.5, 5.8.1; F8 |
| v. Token and latency cost | +187 ms and about 536 prompt tokens per answer (0.5B). The engine itself costs about 29 ms; the rest was CPU contention. | 5.8.10; F8, F12 |

**A3. Were all five objectives met?**
- **i, iv and v: met.**
- **ii (design): met, with two justified deviations.**
  - The default ranking dropped recency and importance because they measurably hurt recall (F1).
  - The distilling write policy is implemented and unit-tested, but the experiments used verbatim notes.
- **iii (develop on a consumer laptop without a GPU): met in substance, with one deviation.**
  - The engine runs CPU-only on an embedded SQLite store.
  - The measurements were taken on laptop-class cloud containers (4 vCPU, 16 GB, no GPU), not on one physical laptop.

  All of these are stated in Chapter 5, "Alignment with the Proposal".

**A4. Why compare against a cloud model if the point is on-device?**
The cloud model is the upper anchor that defines "the gap" (scope, section 1.6). It never runs locally. A frontier anchor (Kimi K3) also keeps "gap closed" on its 0–1 scale; against the weaker gpt-oss-20b it exceeded 1 (issue 4, F7).

**A5. You said 1–3B models in scope but tested 0.5B–14.8B. Why?**
That was an extension, not a change. The 1–3B models were all tested. The smaller (0.5B) and larger (7–14.8B) models were added to locate the edges of the useful range. The result confirms the scope choice: 1.5–4B is the range that suits the engine on a 4-core CPU (5.8.7; F10b).

---

## B. Is this "just RAG"?

**B1. How is CAMR different from retrieval-augmented generation?**
The retrieval core is RAG, and that is deliberate: the study measures how far memory can substitute for model size. CAMR differs in four measured ways:
1. **It is capability-adaptive.**
   - It abstains when nothing is relevant (gating).
   - It admits only notes within 0.15 of the best match.
   - It follows one entity hop (bridging), which took 2Wiki full-support recall from 35.8% to 78.4% (F1b).
2. **Memory grows from use.**
   - Chat statements, "remember that…" commands and 👍-approved answers become memory, with provenance.
   - The same frozen weights went from 6.7% to 66.7% on long-tail facts as memory grew (F2).
3. **It is budget-controlled per model and task.**
   - A learned router picks the budget (or escalates to the cloud) per question.
   - With it, 71% of questions stayed on the device at equal accuracy (F11b).
4. **It is evaluated as a gap-closing mechanism.**
   - Results are reported as gap closed and residual gap, not as raw accuracy only.

**B2. Isn't fine-tuning better?**
Fine-tuning needs compute that users do not have. It has to be redone whenever knowledge changes, and it risks forgetting (Chapter 1, Problem Statement). CAMR adapts through storage instead. A fact is usable the moment it is written, can be removed with "Forget", and leaves the weights unchanged (delimitation: no training or fine-tuning). The learned router is a ridge/LinUCB model over 11 features, not a language model.

**B3. Is there a context-window limit?**
The model only ever reads the notes selected within the budget (128–1,024 tokens), so the store can grow far beyond the context window. Retrieval stayed at a median of 54–64 ms over 38,054 notes (F1b), and the memory-size test in Chapter 5 shows the same in the app. The limit is how many relevant notes fit in the budget, not how many exist.

---

## C. Design decisions

**C1. Why SQLite + sqlite-vec instead of a vector database?**
It is one file, has no server and works on every OS. That meets the embedded-store objective (iii). The search costs about 6 ms (F12), so a dedicated vector database would not buy measurable speed at this scale.

**C2. Why did you drop Equation 4.1 (recency + importance)?**
It lowered full-support recall by 4.6 points on HotpotQA and by 1.2–5.4 points on 2Wiki (F1, F1b). Benchmark questions are independent, so recency carries no signal. The terms are still implemented and switchable; a sessioned benchmark is listed as future work.

**C3. How was the gating threshold chosen?**
It was calibrated, not guessed. The threshold is the 90th percentile of question-to-off-topic-paragraph similarity on 200 HotpotQA questions. For BGE this gives 0.49, so the benchmarks use 0.50. For nomic-embed-text (used by the app) the same rule gives 0.55, which keeps 100% of relevant matches and rejects 89.5% of off-topic ones (`docs/calibration/`).

**C4. Why a 0.15 admission margin?**
It keeps near-ties and drops the long tail of weak matches. In the trace for *The Loudwater Mystery*, one note was admitted at 0.77 and the next (0.62) was excluded, so the model read 47 tokens instead of 500 and answered correctly (F3).

**C5. Is the engine deterministic?**
Yes. Prompts were byte-identical across repeats (30/30, F5). The 0.5B model's answers were not (20/30 identical, with flips only between wrong answers), so floors are reported as a range.

---

## D. Method and validity

**D1. Is the data real?**
Yes. All four benchmarks are public and human-written or Wikidata-derived. The only synthetic data are unit-test fixtures, which never enter a result (FINDINGS §0).

**D2. Could test questions have leaked into memory?**
No. A holdout guard keeps every evaluation question out of the store. The learned policy was trained on 144 questions disjoint from the 72 held-out ones. The n = 200 run fixed the configuration before it ran (5.3, 5.4).

**D3. Thirty questions is small. How confident are you?**
For the pilot, not very; one question is 3.3 points. That is why:
- the multi-hop result was re-run on 200 questions, where every gain's 95% CI excludes zero (F13);
- the retrieval study used 500 questions per benchmark;
- gap closed is reported with bootstrap CIs.

The single-hop and maths results rest on the pilot and are flagged as such.

**D4. Kimi only runs at temperature 1. Doesn't that make the ceiling unstable?**
Yes. Kimi's scores are single samples, as stated in the limitations, and the model version was pinned (delimitation). The headline n = 200 comparison has the small model at 54.0% against Kimi at 51.8%; that is a match, not a win.

**D5. Why exact match? Isn't it too strict?**
It is strict. Some of the 0.5B model's "misses" name the right person in a sentence (F4). EM, contains and F1 are all logged. EM is used for multi-hop so that results are comparable with the HotpotQA literature, and the strictness counts against CAMR, not for it.

**D6. Measurements were on cloud containers. Do they transfer to a laptop?**
Accuracy does: decoding is greedy and the engine is deterministic. Speed is indicative, as limitation 1 of Chapter 1 anticipated. The containers match the scope's laptop class (4 cores, 16 GB, no GPU), and the full specification is reported. The app's latency table can be re-run on any machine with `python scripts/app_latency.py`.

**D7. What did the AI assistant do, and how do you know the results are real?**
Claude Code helped write code, run experiments and draft text under my direction (Chapter 5, AI declaration). Every number names its results file, the per-query logs store prompts and answers, and 105 automated tests cover the engine and app. Any table can be regenerated from the repository.

---

## E. Results

**E1. What is the single strongest result?**
On 200 held-out multi-hop questions, a 3B model on a 4-core CPU with CAMR matched a frontier cloud model (54.0% vs 51.8%) at about a third of its answer time (5.8 s vs 18.4 s). The configuration was fixed in advance (F13).

**E2. Where does it not work?**
Mathematical reasoning: the residual gap is 83 points, and worked-example memory hurt 7 of 19 models (F8, F10b). It also does not help when the evidence is present but the model misreads it; 76% of the 0.5B model's multi-hop misses had the answer in context (F4).

**E3. Does a bigger small model always help?**
Not for facts. From 1.5B up, every model reached 70–80% with memory, and 14B was no better than 1.5B (F10b). For multi-hop, yes up to about 3B, though family matters: mistral:7b (43.3%) did worse than llama3.2:3b (56.7%).

**E4. Did the learned policy really beat the cloud?**
No, it matched it. The policy scored 65.3% against 63.9% for always-Kimi, which is within noise. The robust result is equal accuracy with 71% of questions kept on the device and a 4.0× lower mean latency (3.1 s vs 12.6 s) (F11b).

**E5. Why does more memory sometimes lower accuracy?**
Small models are distracted by extra notes. For the 0.5B model, accuracy on facts at 128 tokens was 76.7%, against 66.7% at 512 and 1,024 (F8). This is why the budget is adaptive.

---

## F. Speed and latency

**F1. What does the engine itself cost?**
About 29 ms per question in isolation: embedding 21.5 ms, search 6.2 ms, bridging 1.2 ms and packing 0.4 ms (F12). The rest of the measured 187 ms was the embedder and model competing for four cores. Partitioning threads cut the p90 from 157 to 50 ms.

**F2. Why did NFR-02 (retrieval ≤ 10% of answer time) fail?**
A 0.5B model answers in about 180 ms, so even 29 ms is about 16% of the answer time. The target is reachable for models whose generation takes 450 ms or more, roughly 1.5B and above on this CPU (F12). The requirement was reported as not met rather than redefined.

**F3. What did you do to make the app faster?**
Three changes, measured in Chapter 5, "Responsiveness of the Application":
1. **Warm-up.** The app loads the chat model when it starts and when the user switches model, so the first answer does not wait for the model to load.
2. **Time to first word.** Answers stream, and the app now measures and shows how long the first word took. This is what users perceive.
3. **Query-embedding cache.** A repeated question skips the embedding call.

Earlier engine-level gains were gating (fewer tokens: 1.7–3.4× faster per answer than the baseline, F8) and thread partitioning (F12).

**F4. What else would make it faster?**
- A GPU or NPU, which would cut decode time by an order of magnitude.
- Reusing the model's prompt cache by putting the fixed instructions first.
- Smaller budgets for small models, which are also more accurate (E5).
- Lighter quantisation for prefill-bound CPUs.
- Embedding on a separate core.

These are listed as recommendations in Chapter 6.

**F5. Is the local model faster than the cloud?**
For 0.5B–4B, yes. With memory, those models took 1.4–5.8 s per answer, against 7.7–18.8 s for Kimi K3. Models of 7B and above with memory were slower than the cloud on this CPU (F10b).

---

## G. The application (CAMR Personal)

**G1. Wasn't an end-user app out of scope?**
Yes. Chapter 1 scoped a read-only inspector, and that was delivered. CAMR Personal is an extension built after the experiments were complete, so that the findings could be used and tested by real users. It is reported as such and does not replace any scoped deliverable.

**G2. Is user data safe?**
- The app binds to 127.0.0.1 and refuses foreign Host headers and cross-site writes (TC-31).
- It serves no files outside the app (TC-32).
- The model runs locally through Ollama.
- Feedback export is opt-in and metrics-only by default.

No user study has been run, and ethics approval is recommendation 8 in Chapter 6.

**G3. How does it "grow with the user"?**
- What the user says, explicit "remember that…" commands and 👍-approved answers are stored as memory with provenance.
- The growth panel shows memory size and the share of answers drawn from memory.
- The weights never change.

Whether real users find it more useful over weeks is the first future-work item; it is not yet a finding.

**G4. Why is there no phone version?**
Porting to mobile was delimited out in Chapter 1. An Android prototype was started (a Kotlin engine port with 6 unit tests passing, and a 57 MB APK built), but it has never run on a device. It is therefore reported as future work in Chapter 6, not as a result.

**G5. Which platforms are supported?**
Windows x64/ARM64, macOS Apple Silicon/Intel and Linux x64/ARM64. Continuous integration builds and launch-tests each one, and release v0.2.0 carries all six downloads.

---

## H. Reflection

**H1. What would you do differently?**
- Run n ≥ 200 for every task from the start.
- Measure on a physical laptop alongside the containers.
- Use a sessioned benchmark, so that the recency design could be tested fairly.

**H2. What is the contribution in one line?**
Measured evidence that external memory lets 1.5–4B models on a CPU match a frontier cloud model on knowledge-bound questions, together with the residual gap that memory cannot close, released as open-source software that people can use.
