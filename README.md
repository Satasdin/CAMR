# CAMR: Capability-Adaptive Memory Retrieval

CAMR is a lightweight external memory engine that sits beside a frozen 1–3B
language model on a consumer laptop. It comes with an evaluation harness that
measures how much of the small-versus-large capability gap the memory closes,
per task type, with token and latency accounting.

```
                write path (ingest)                             read path (per question)
 source text ─▶ WritePolicy ─▶ NoteScreener ─▶ importance ─▶ Embedder ─▶ ┌──────────────┐
                (verbatim |     (empty, dup,    + timestamp                │  camr.sqlite │
                 structured)     injection…)                               │ notes + vecs │
                                                                           │ + provenance │
 question ─▶ Embedder ─▶ kNN (sqlite-vec) ─▶ RetrievalPolicy ─▶ TokenBudgeter ─▶ PromptTemplate ─▶ frozen SLM
                                            sim·w_s + rec·w_r + imp·w_i   Σ tokens ≤ B           (Ollama)
```

- **Engine** (`camr.memory`): write policies, screener, importance, BGE
  embedder, a single-file SQLite store with sqlite-vec search, retrieval
  policies (Eq. 4.1–4.4), and the token budgeter (Eq. 4.5). It is usable as a
  library without the harness.
- **Harness** (`camr.harness`, `camr.eval`): benchmark loaders, floor / ceiling
  / treatment runners, scorers, per-query logging, gap closed with paired
  bootstrap CIs (Eq. 3.1), the ablation and budget sweep, the device profiler,
  and a failure-decomposition diagnostic.
- **Inspector** (`camr.inspect`): a read-only Streamlit UI with Run Dashboard,
  Ablations, Query Trace and Memory Store screens.

**Want to use it?** [`docs/APP.md`](docs/APP.md): install CAMR Personal and give any Ollama model a memory that grows (`camr app`).

**New here?** Follow [`docs/SETUP.md`](docs/SETUP.md), a step-by-step walkthrough with annotated screenshots. Measured results are in [`docs/FINDINGS.md`](docs/FINDINGS.md). The Android personal-assistant application is in [`docs/ANDROID_ASSISTANT.md`](docs/ANDROID_ASSISTANT.md).

See [`docs/BRIDGING_THE_GAP.md`](docs/BRIDGING_THE_GAP.md) for what "bridging
the gap" can and cannot mean, the four capability-adaptive mechanisms, and six
falsifiable predictions. See [`docs/DESIGN_NOTES.md`](docs/DESIGN_NOTES.md) for a
critique of the proposal and every place the implementation departs from it.

## What makes it capability-adaptive

| Mechanism | Gap it targets | Config |
|---|---|---|
| **Gating**: abstain when the best note is weak; admit only notes near the best one | Reading (distraction) and cost | `min_similarity`, `similarity_margin` |
| **Entity-bridge expansion**: a note's mention of another entity pulls in that entity's notes, with no model call | Multi-hop knowledge | `expansion: entity` |
| **Procedural memory**: worked solutions from the train split for reasoning tasks | Reasoning | `reasoning_memory: exemplars` |
| **Escalation curve**: gap closed vs share of queries sent to the cloud | The residual | `tables/escalation.md` |
| **`ceiling_rag` condition**: the cloud model with the same notes | Measures the *residual* gap | `extra_conditions: [ceiling_rag]` |

## Install

```bash
pip install -e ".[vec,embed,dev]"   # engine + sqlite-vec + BGE + tests
pip install -e ".[cloud]"           # ceiling condition (Anthropic SDK)
pip install -e ".[inspect]"         # Streamlit inspector + figures
ollama pull qwen2.5:3b              # local model (also llama3.2:3b, phi3:mini)
export ANTHROPIC_API_KEY=...        # only the ceiling condition uses the network
```

After the first run has downloaded the BGE model, set `HF_HUB_OFFLINE=1` so
nothing but the ceiling condition ever touches the network (NFR-06).

## Data

Download the official distributions into `data/`. Paths are set in
`configs/default.yaml`.

| Benchmark | File | Task type |
|---|---|---|
| PopQA | `data/popqa/test.tsv` **plus** `data/popqa/corpus.jsonl` (`{doc_id,title,text}`, e.g. Wikipedia pages of `s_wiki_title`) | single-hop |
| HotpotQA | `data/hotpotqa/hotpot_dev_distractor_v1.json` | multi-hop |
| 2WikiMultiHopQA | `data/2wikimultihopqa/dev.json` | multi-hop |
| GSM8K | `data/gsm8k/test.jsonl` **plus** `data/gsm8k/train.jsonl` (exemplars) | reasoning |

PopQA ships no documents, so you have to supply its corpus (see design note
A4). Memory is built only from supporting and distractor paragraphs. The
holdout guard refuses to ingest any document that contains an evaluation
question verbatim.

## Run

```bash
camr reproduce --config configs/default.yaml        # everything, one command (NFR-04)

# or step by step
camr ingest    --config configs/default.yaml
camr run       --config configs/default.yaml --condition floor     --benchmark popqa
camr run       --config configs/default.yaml --condition ceiling   --benchmark popqa
camr run       --config configs/default.yaml --condition treatment --benchmark popqa --budget 512
camr run       --config configs/default.yaml --condition ceiling_rag --benchmark popqa
camr ablate    --config configs/default.yaml
camr analyse   --run-dir results/2026-09-29
camr profile   --config configs/default.yaml --repeats 5
camr inspect   --run-dir results/2026-09-29

# deployment scenario: your own documents, one question, fully local
camr ingest --config configs/default.yaml --corpus my_notes.jsonl --out results/mine
camr ask    --config configs/default.yaml --out results/mine "Who founded Acme Rockets?"
```

Offline smoke test (dry-run models, hashing embedder, fixture data; the numbers
are meaningless):

```bash
camr reproduce --config configs/smoke.yaml
```

Runs are resumable. A completed run with the same label and configuration hash
is skipped, and ingestion skips sources already committed.

## Outputs

```
results/YYYY-MM-DD/
  camr.sqlite          notes, embeddings, provenance, rejections, runs, query logs, scores, retrieval traces
  records/*.jsonl      one structured record per query
  samples/*.json       the fixed paired sample per benchmark (seed + source hash)
  tables/gap_main.md   floor / ceiling / treatment / ceiling_rag, gap closed + 95% CI, residual gap, abstain rate
  tables/ablation.md   Δ gap closed, Δ tokens/query, Δ latency vs control (Table 4.7)
  tables/budget_sweep.md, budget_optimum.json   objective v: best budget per token, saturation point
  tables/coverage.md   where answers are lost: store → candidates → context → correct
  tables/escalation.md gap closed vs escalation rate, with random and oracle routers
  tables/profile.json  hardware spec, median latencies, retrieval share (NFR-02), peak RSS (engine + model runtime)
  tables/templates.md  every prompt template, verbatim (DR-09)
  figures/*.png        (when matplotlib is installed)
  config.yaml
```

## Configuration (Table 4.6)

| Key | Default | Ablation |
|---|---|---|
| `memory.write_policy` | `structured` | `verbatim` |
| `memory.retrieval_policy` | `composite` | `similarity_only` |
| `memory.weights` | 0.60 / 0.15 / 0.25 | 1 / 0 / 0 in control |
| `memory.recency_decay` | 0.99 per hour (per question step) | fixed |
| `memory.k` | 20 | 10, 50 |
| `memory.token_budget` | 512 | 0, 128, 256, 512, 1024, 2048 |
| `memory.screening` | `true` | `false` |
| `memory.normalise_similarity` | `true` | `false` |
| `memory.packing` | `greedy_stop` | `greedy_skip` |
| `memory.importance` | `heuristic` | `model` |
| `memory.min_similarity` / `similarity_margin` | 0.50 / 0.15 | 0 / off in `control` … `composite` |
| `memory.expansion` | `entity` | `none` |
| `memory.reasoning_memory` | `exemplars` | `facts`, `none` |

## Tests and traceability

```bash
pytest            # 81 tests, fully offline
```

| Test case | Requirement | Test |
|---|---|---|
| TC-01 | FR-01 write policies | `test_verbatim_policy_*`, `test_structured_policy_*` |
| TC-02 | FR-02/03, DR-06 screening + provenance | `test_screener_*`, `test_ingest_logs_rejections_with_provenance`, `test_checksum_uniqueness_is_enforced_by_schema` |
| TC-03 | FR-04, IR-03 | `test_committed_notes_have_timestamp_importance_embedding` |
| TC-04 | FR-05, IR-04, NFR-03 | `test_store_knn_get_and_stats`, `test_vector_backends_agree` |
| TC-05 | FR-06/07 | `test_similarity_only_*`, `test_composite_*`, `test_equations_4_3_and_4_4` |
| TC-06 | FR-08 | `test_budget_is_never_exceeded`, `test_greedy_stop_admits_a_prefix_and_skip_fills` |
| TC-07 | FR-09, IR-01 | `test_model_runner_exposes_only_generate`, `test_ollama_runner_*` |
| TC-08 | FR-10, IR-02, NFR-09 | `test_cloud_runner_*` |
| TC-09 | FR-11, DR-02 | `test_sample_is_fixed_persisted_and_order_invariant` |
| TC-10 | FR-12 | `test_scoring_metrics` |
| TC-11 | FR-13, NFR-08 | `test_records_are_complete_and_prompts_byte_identical` |
| TC-12 | FR-14, NFR-07 | `test_ablation_plan_covers_variants_and_sweep` |
| TC-13 | FR-15 | `test_gap_closed_and_bootstrap`, `test_gap_flags_unstable_denominator` |
| TC-15 | FR-17, IR-06 | `test_inspector_cannot_write`, `test_nothing_depends_on_inspect` |
| TC-18 | NFR-04, IR-05 | `test_cli_reproduce_with_dry_run_models`, `test_reproduce_end_to_end_and_memory_closes_the_gap` |
| TC-19 | NFR-05 | `test_records_are_complete_and_prompts_byte_identical`, `test_recall_is_deterministic_after_reset` |
| TC-20 | NFR-06 | `test_only_ceiling_touches_the_cloud_runner` |
| TC-21 | DR-03/04 | `test_holdout_guard`, `test_popqa_requires_a_corpus` |
| TC-22 | IR-07 | `test_runtime_down_logs_failures_and_continues` |
| P2–P6 | Bridging mechanisms | `tests/test_bridging.py` |

TC-14 and TC-17 (device memory, NFR-02 retrieval share) are measurements.
`camr profile` produces them on the target laptop.

## Package layout (Figure 4.6)

```
camr/config.py     single Config object (leaf module; rejects unknown keys)
camr/memory/       note, clock, embedder, importance, screener, write_policy, store, retrieval, budgeter, engine
camr/models/       runner (Ollama, Cloud, DryRun), prompt templates, tokenizer
camr/harness/      benchmarks, experiment (Workspace, ExperimentRunner), ablation, profile, diagnostics
camr/eval/         scoring, logger (harness schema), analysis (GapAnalyzer), report
camr/cli/          the command surface
camr/inspect/      read-only Streamlit inspector
```
