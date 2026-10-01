# CAMR design notes: critique of the proposal and what the implementation changes

This document reviews the CAMR project proposal (Chapters 1–4) against what
building the engine actually required. Each item says what the problem is, why
it matters for the study's claims, and what the code does about it. Items are
ordered by how much they could distort the reported numbers.

---

## A. Issues that would bias or invalidate results

### A1. Recency under a static benchmark is order-dependent and breaks NFR-05
**Proposal.** Recency is `δ^Δt` over hours since last access (Eq. 4.3). Section
4.4.7 already notes that batch ingestion makes creation times identical, so
recency is "driven by access during evaluation".

**Problem.** With wall-clock time, Δt depends on how fast the laptop answers
each question. The same configuration then produces different rankings on
different runs, which directly violates NFR-05 (byte-identical prompts). There is
a second, subtler problem. Benchmark questions are independent, so a note admitted for
question *i* gets a recency boost for question *i+1* even though the two are
unrelated. On PopQA, HotpotQA and GSM8K, recency is a feedback loop that rewards
whatever was retrieved last. The expected effect is zero or negative, not
positive.

**Change.**
- `LogicalClock` (`camr/memory/clock.py`) advances a fixed step per question, so
  Δt means "questions since last access". The clock is deterministic and
  independent of the machine.
- `reset_access_state()` restores every note to its ingested state at the start
  of every run, so all conditions and ablations start from the same store.
- The Memory Store Browser takes "ever retrieved" from the `retrieved_note` log,
  not from the access counters, which are reset.
- **Recommendation:** report the recency ablation as a test of whether recency
  *hurts* on independent questions. The literature review already cites the right
  instrument for a positive test, a sessioned benchmark such as LongMemEval or
  LoCoMo, where recency carries real signal. A small LongMemEval subset would
  make the recency claim defensible.

### A2. Equation 4.1 adds terms on different scales
**Problem.** Recency and importance lie in [0, 1], and importance is min-max
spread across the full interval. Raw BGE cosine similarity sits in a narrow band
(about 0.3–0.9), so a small importance difference can outweigh a large relevance
difference. Park et al. (2023), whose formula this is, min-max normalise *all
three* terms.

**Change.** `normalise_similarity: true` (the default) min-max scales similarity
over the candidate set before weighting. Min-max is monotone, so the
similarity-only control ordering is unchanged. The raw cosine is still what gets
logged as `similarity`.

### A3. Equation 3.1 is unstable when ceiling ≈ floor
**Problem.** Gap closed is a ratio. If the ceiling barely beats the floor on a
task type (plausible on GSM8K with a strong 3B model), a 2-point wobble becomes
±0.5 "gap". The denominator can even go negative inside a bootstrap resample.

**Change.** `GapAnalyzer` always reports `absolute_gain` (S_T − S_F) next to the
gap. It flags `unstable` when the denominator is below `min_denominator` (default
0.05), leaves the gap undefined instead of printing a meaningless number, and
reports the share of bootstrap resamples with a usable denominator. Negative gaps
(memory hurts) are reported, not clipped.

### A4. PopQA has no "accompanying document collection"
**Problem.** DR-03 says the store is populated from "the supporting document
collections that accompany the factual benchmarks". PopQA ships only
question/answer triples. The proposal does not say where its documents come
from.

**Change.** `benchmarks.popqa.corpus` is mandatory, and the loader fails loudly
without it. It accepts `{doc_id,title,text}` JSONL (for example, the Wikipedia
page of each `s_wiki_title`) or Mallen et al.'s per-question `ctxs` retrieval
dumps. **Recommendation:** using the subject's own page approximates oracle
retrieval. State this in the method, and add non-target pages as distractors
(A5).

### A5. The store is unrealistically small and easy
**Problem.** Building memory only from the paragraphs of *sampled* questions
gives about 10 paragraphs × 400 questions per benchmark. Retrieval over roughly
4k notes is easy, and profiling at that size under-states latency for a real
assistant.

**Change.** `extra_corpus_questions` adds paragraphs from unsampled questions
(still never their QA records) to grow the store. **Recommendation:** run
`camr profile` at 2–3 store sizes so NFR-02 is tested at a realistic scale.

### A6. Write-policy and screening ablations need separate note populations
**Problem.** Table 4.7 compares verbatim with structured notes, and Table 4.6
switches screening on and off. Both change what is *stored*. The proposal has one
store and one ingestion pass, so these ablations are impossible without
rebuilding the store, which would change everything else too.

**Change.** Each (write policy, screening) combination is its own note
population, keyed by `note.note_type` (`verbatim`, `structured`,
`structured-unscreened`, …), inside the same single file. Retrieval filters by
population. Checksums are namespaced by population, so the schema's UNIQUE
constraint still rejects duplicates within a population, even with screening
off, as §4.4.6 promises.

### A7. There was no way to tell *where* a knowledge-bound answer is lost
**Problem.** A wrong treatment answer could be caused by the write policy
dropping the fact, the embedder missing it, the ranking or budget cutting it, or
the model misreading it. The Query Trace screen diagnoses one question. Nothing
diagnoses the sample.

**Change.** `camr/harness/diagnostics.py` writes `tables/coverage.md`. For every
treatment run, it reports the fraction of questions whose gold answer is in the
store, in the k candidates, in the admitted context, and answered correctly,
plus correctness *given* the answer was in context. The offline smoke test
already shows its value: a crude distiller drops a fact and `answer_in_store`
falls from 1.0 (verbatim) to 0.5 (structured).

### A8. Structured notes can hallucinate, and the screener cannot see it
**Problem.** The same small model that is weak on facts rewrites the facts at
ingestion. Screening catches degenerate output, not factual drift.

**Change / recommendation.** `answer_in_store` (A7) measures fact retention
directly. Report it for verbatim vs structured, because it is the cost side of
the density trade-off. The distillation prompt asks the model to keep names,
dates and numbers verbatim, and the passage title is re-attached when the model
drops it.

---

## B. Under-specified design points

| Item | Proposal | Implementation |
|---|---|---|
| Importance score (FR-04) | Required, never defined | `heuristic` (default): factual density from entity-like tokens, numbers and lexical variety, at zero cost. `model`: Park-style 1–10 rating from the local model. The method is recorded in the config. |
| Token counting for the budget | Unspecified tokenizer | Budget enforced with a fast model-agnostic regex tokenizer. The model's own `prompt_eval_count` is logged as `prompt_tokens`, and an exact HF tokenizer is optional. |
| Greedy packing (Eq. 4.5) | Stop at first breach | Kept as default (`greedy_stop`). `greedy_skip` is offered as an ablation, because one long top note can otherwise leave most of the budget unused. |
| Budget = 0 | In the sweep | Uses the memory template with an empty notes section, so `budget-0` vs floor isolates the template effect from the memory effect. |
| "Approximate" NN search | ANN via extension | sqlite-vec `vec0` is *exact* kNN. At these store sizes that is fast and removes ANN recall as a confound. An exact NumPy fallback over the same BLOBs gives identical scores (tested). |
| Failures | IR-02/IR-07 | Failed queries are logged with `status='failed'` and excluded from scoring. Pairing uses only questions answered under all three conditions, and failures are counted per group. |
| Sample reuse | "drawn once" | Persisted to `samples/<benchmark>.json` with seed and source-file hash. The draw is invariant to dataset file order. `--n` takes a prefix and never re-draws. |
| Answer extraction | Unspecified | The first line minus an "Answer:" lead-in is scored for EM/F1. PopQA defaults to `contains` (Mallen et al.'s accuracy). GSM8K uses the final number. The same extraction applies to every condition. |
| Retrieval scope for GSM8K | Unspecified | The reasoning control retrieves from the *whole* store (irrelevant factual notes). This is realistic, and it tests whether memory *distracts* reasoning. |

---

## C. Architecture corrections

- **Config location.** Figure 4.6 puts configuration in `camr.cli`, but
  `camr.memory` needs it, and memory must not depend on cli. Config is now a leaf
  module, `camr/config.py`, that rejects unknown keys so ablation typos fail
  loudly.
- **Dependency rules are tested.** `tests/test_architecture.py` enforces that
  `memory` does not import `harness/eval/cli/inspect`, `eval` does not import
  `memory`, and nothing imports `inspect`.
- **Read-only inspector by construction.** SQLite is opened with `mode=ro`, so
  writes fail at the driver, not by convention.
- **Figure 4.3 is not a class diagram.** It shows entities with typed fields
  (`model_runner.model_name`, `prompt_template.body`) and no operations or
  inheritance, so it is an ER diagram. The classes the text describes
  (`WritePolicy` ← `Verbatim`/`Structured`, `RetrievalPolicy` ←
  `SimilarityOnly`/`Composite`, `ModelRunner` ← `Ollama`/`Cloud`) exist in the
  code and should be drawn as UML classes.

---

## D. Device measurement

- **Peak memory missed the model.** "Peak process memory" (FR-16) measured in
  the harness process excludes the quantised model, which Ollama serves from a
  *separate* process and which dominates the 16 GB budget. `camr profile` reports
  both the engine process and the runtime process (`VmHWM`).
- **Cold start.** The first query includes model load. The profiler warms up the
  model and embedder before timing.
- **Offline guarantee (NFR-06).** The BGE model is downloaded from Hugging Face
  on first use. Set `HF_HUB_OFFLINE=1` after the first download, and `ollama pull`
  models beforehand. The local runner refuses non-loopback hosts, and a test
  monkeypatches sockets to prove floor and treatment runs open no external
  connection.

---

## E. The ceiling model

- Pinned to `claude-opus-5-5` (NFR-09). The served model id is logged per query,
  and any drift shows up in `run.model_version`.
- **Server-side model fallbacks are deliberately *not* enabled.** A fallback
  would answer with a different model and silently move the ceiling. A refusal is
  logged as a failed query instead.
- This model has adaptive thinking always on, and sampling parameters are not
  accepted, so the ceiling cannot be greedy-decoded the way the local model is.
  The ceiling is therefore a stochastic anchor. Treat its run as fixed once
  logged: re-analysis reuses the logged answers and never re-queries.
  `ceiling_model.effort` is recorded in the run config because it moves the
  anchor.
- SDK retries are disabled so the retry/backoff policy is the one the study
  specifies (IR-02) and is testable.

---

## F. Errors in the proposal document

- **FR-01 rationale** cites "(Chen, 2024) on context density". Chen (2024) is
  AgentPoison, a memory-poisoning paper. Context density is Jiang et al. (2023,
  LLMLingua) or Chevalier et al. (2023).
- **§3.5.3** cites "Yang A., 2024" (the Qwen2.5 report) for HotpotQA. It should
  be Yang Z. et al. (2018).
- **Duplicated in-text citations** from the reference manager: §2.2.1 "(Abdin …;
  Abdin …)", §2.2.2 "(Mallen …; Mallen …)", §2.2.3 "(Borgeaud …; Borgeaud …)".
- **§3.4** ends with a double full stop.
- **Test cases** are "realised in section 5.4.2", which does not exist yet. They
  are now realised as tests named by TC id in `tests/` (see the README's
  traceability table).

---

## G. Scope kept deliberately out

- **Graph associative layer (FR-18, "Could").** Superseded by entity-bridge
  expansion (`memory.expansion: entity`; see `BRIDGING_THE_GAP.md` §3.2), a
  one-step spreading activation over entity titles that needs no graph
  construction and no model call. A full PPR graph can still be added through
  the retrieval-policy registry. `graph_layer: true` fails loudly.
- **Write-back during evaluation** is off. It would change the store between
  paired questions. `MemoryEngine.write_back` exists for the deployment scenario
  (`camr ask`).
