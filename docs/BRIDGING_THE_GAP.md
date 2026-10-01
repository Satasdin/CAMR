# Bridging the capability gap: an objective re-think

The title promises to *bridge the capability gap between on-device and cloud
language models*. This note asks whether the proposed engine can do that,
where it cannot, and what changes would make the claim both true and testable.
It also records what is now implemented.

---

## 1. The gap is four gaps, not one

When a 3B model loses to a frontier model on a question, the loss has one of
four causes:

| Component | What the small model lacks | Can external memory help? |
|---|---|---|
| **Knowledge** | The fact was never memorised (long-tail entities) | **Yes.** This is what RAG does (Mallen et al., 2023). |
| **Reading** | The fact is in the prompt, but the model fails to use it or is distracted by irrelevant notes | Only indirectly, by supplying *less and better* context |
| **Reasoning / procedure** | Cannot carry out the multi-step computation | Not with facts. Possibly with **worked examples** (procedural memory). |
| **Calibration** | Does not know when it does not know | Memory can provide a confidence signal (retrieval strength) |

The proposal's engine targets the first row only. That is legitimate, but then
"bridging the gap" has to be reported as *which part* of the gap was bridged,
not as one number.

## 2. Problems with the current experiment

**2.1 The headline is close to predetermined.** The store is built from the
supporting paragraphs of the very questions being asked. On PopQA the answer is
in the subject's own page. The treatment is therefore an *open-book* exam and
the ceiling a *closed-book* one. A large "gap closed", possibly above 1 on
PopQA, would show that open-book beats closed-book, which Lewis et al. (2020) and
Mallen et al. (2023) already established. It would not show that memory
substitutes for scale.

**Fix.** Add a fourth condition, **`ceiling_rag`**: the large model reads the
*same* recalled notes. Then:

```
total gap            = S_ceiling      − S_floor
knowledge gap closed = S_treatment    − S_floor
residual gap         = S_ceiling_rag  − S_treatment   ← the part memory cannot buy
```

The **residual gap** compares the two models when both have the same knowledge.
It is the honest measure of what scale still provides (reading and reasoning),
and the honest answer to "is memory a substitute for scale?".

**2.2 Nothing is capability-adaptive.** Every question gets the same 512 tokens
of memory, whether retrieval found something relevant or not. Mallen et al.'s
key practical result was *adaptive* retrieval: retrieve only when the model is
unlikely to know, which improved accuracy *and* cut cost. Small models are also
more easily distracted by irrelevant context than large ones. Always injecting
notes can make answers *worse*, and the fixed-budget design cannot see this.

**2.3 Single-shot retrieval cannot do multi-hop.** For "the university attended
by the founder of Acme Rockets", the question embedding finds the Acme note.
The MIT note shares almost nothing with the question. Iterative retrieval
(retrieve, read, retrieve again) costs a model call per hop, which is expensive
on a CPU.

**2.4 The reasoning control is designed to fail.** Feeding factual notes to
GSM8K tests nothing except distraction. A null result there is not informative.

**2.5 The cost model points at the wrong thing.** Retrieval takes milliseconds.
The real cost of memory on a CPU is **prefill**: a 3B Q4 model processes on the
order of tens to a few hundred prompt tokens per second on a laptop CPU. That
makes 512 memory tokens seconds of added latency. NFR-02 ("retrieval ≤ 10%")
will pass trivially while the user waits on prefill. The budget is a *latency*
knob, and the metric that matters is **added end-to-end latency vs floor**.

## 3. What CAMR should be

The engine becomes *capability-adaptive* in four concrete ways. All are cheap,
and none needs an extra model call on the read path.

### 3.1 Adaptive gating: memory only when it is likely to help
- **Abstain.** If the best note's similarity is below `min_similarity`, supply
  no memory and answer exactly like the floor. Irrelevant notes cannot distract.
- **Relevance margin.** Admit only notes within `similarity_margin` of the best
  one. The budget becomes a *ceiling*, not a target: easy questions use 40
  tokens, hard ones up to the budget.

This directly serves objective v (gap closed per token), because tokens are
spent only where they buy accuracy.

### 3.2 Entity-bridge expansion: multi-hop with no extra model call
A HippoRAG-style one-step spreading activation, in a lightweight form. Every
note keeps its source title, the entity it is about. After first-stage ranking,
the top seed notes are scanned for mentions of other titles in the store. The
notes about those entities are inserted directly after their seed. "Acme Rockets
was founded by **Jane Holt**" pulls in the Jane Holt note. "Jane Holt studied at
**MIT**" would pull in the MIT note on a second step. Cost: a dictionary scan of
a few notes, a fraction of a millisecond. This replaces the optional graph layer
(FR-18) with something cheap enough to be core.

### 3.3 Procedural memory for reasoning
For reasoning tasks the engine retrieves from a separate **exemplar**
population: worked solutions from the GSM8K *train* split, never test (the
holdout guard checks this). Similar solved problems are placed in the prompt as
examples. This turns the reasoning control from a designed null into a second
hypothesis: *knowledge memory helps knowledge tasks; procedural memory helps
procedure tasks; neither helps the other.*

### 3.4 Escalation: the practical bridge
Some residual gap will always remain. The deployable answer is a **hybrid**:
answer locally with memory, and send only the least-confident queries to the
cloud. CAMR already logs everything needed to simulate this at zero extra cost.
It uses the treatment answers, the ceiling answers, and a confidence signal from
retrieval strength plus abstention-like answers ("unknown", "I don't know").
`tables/escalation.md` reports gap closed against the fraction of queries
escalated, alongside an *oracle router* upper bound. This turns "bridging"
into a curve a designer can act on. For example, "memory alone closes 0.45;
memory plus escalating 15% of queries closes 0.80, while 85% of queries never
leave the device."

## 4. Falsifiable predictions

| # | Prediction | Refuted if |
|---|---|---|
| P1 | Memory closes most of the **knowledge** gap: PopQA gap closed ≥ 0.5 | gap CI upper bound < 0.5 |
| P2 | A **residual gap** remains on multi-hop even with equal knowledge: `S_ceiling_rag − S_treatment` > 0 | residual CI includes 0 |
| P3 | Entity-bridge expansion raises multi-hop `answer_in_context` and gap closed, at < 5 ms added retrieval | no change in coverage, or latency cost > 5 ms |
| P4 | Adaptive gating matches fixed-budget accuracy with fewer tokens per query, i.e. higher gap closed per 1k tokens | per-token efficiency not higher |
| P5 | Factual memory does **not** help GSM8K (gap ≈ 0 or negative); exemplar memory **does** (gap > 0) | exemplar gap CI includes 0 |
| P6 | Escalating ≤ 20% of queries, chosen by confidence, reaches ≥ 0.8 gap closed overall | curve below 0.8 at 20% |

P2 and P5 are the scientifically interesting ones. P2 says *how much of the
gap is not knowledge*. P5 separates what memory is from what it is not.

## 5. Threats this re-framing introduces

- **`ceiling_rag` sends notes to the cloud.** They are public benchmark text,
  but this widens NFR-06 from "questions only" to "questions and public notes".
  It is opt-in (`extra_conditions: [ceiling_rag]`) and is documented.
- **Thresholds need calibration.** `min_similarity` depends on the embedder.
  Calibrate it on a held-out slice (not the evaluation sample), using
  `answer_in_candidates` from the coverage table, and report the value used.
- **The escalation curve is a simulation from logs.** It assumes cloud answers
  are independent of the routing decision, which is true for a single-turn QA
  benchmark.
- **The bridge heuristic matches titles literally.** Aliases ("MIT" vs
  "Massachusetts Institute of Technology") are missed. That gives a conservative
  estimate of what association can do.

## 6. Implementation map

| Mechanism | Config | Code |
|---|---|---|
| Abstain + relevance margin | `memory.min_similarity`, `memory.similarity_margin` | `MemoryEngine.recall` → `_gate` |
| Entity-bridge expansion | `memory.expansion: entity`, `expansion_seeds`, `expansion_per_seed` | `MemoryEngine._expand`, `SQLiteVectorStore.title_index` |
| Procedural memory | `memory.reasoning_memory: exemplars`, `benchmarks.gsm8k.exemplars` | `build_exemplars`, `MATH_EXEMPLAR` template, `exemplar` population |
| Residual gap | `extra_conditions: [ceiling_rag]` | `ExperimentRunner`, `GapResult.residual_gap` |
| Escalation curve | (analysis only) | `camr/eval/escalation.py` → `tables/escalation.md` |
