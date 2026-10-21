# Engine bench: CAMR's read path on ten memory abilities

`scripts/engine_bench.py` scores the read path CAMR Personal uses, with no model in the loop. Each question
is scored from what that read path admits into the context: did every needed fact get there (all-needed
recall), what share of the context is something else (distractor share), how many tokens, how many
milliseconds, and whether memory abstained. Scoring rules live in `camr/eval/abilities.py` and are unit
tested in `tests/test_abilities.py`.

This is the measurement step. Fixing what it finds is Phase 2.

* `scorecard.md`, `scorecard.json`: the scorecard (generated; do not edit by hand).
* `records/*.jsonl`: one line per question (or per check), what the scorecard is computed from.
* Baseline summary: [below](#baseline-2026-10-21).

## The read path under test

Exactly what `camr.app.assistant.Assistant.__init__` builds, with the BGE embedder (`BAAI/bge-small-en-v1.5`):
verbatim notes (chunks of 120 tokens, 16 overlap), similarity-only ranking, abstain when the best note is
below 0.50, admit only notes within 0.15 of the best, entity gate, entity-bridge expansion, 20 keyword
(BM25) hits joined to 20 vector hits, 384-token budget, sqlite-vec. The bench constructs `Assistant` itself
(learning online off, a session that refuses any network call) and asks `assistant.engine.recall(question)`,
so a change to the app's read path shows up here.

Passage vectors are computed once and cached in `$CAMR_BENCH_HOME/embeddings.sqlite` (on Apple's GPU when
there is one: the same vectors as the CPU to 2e-7 in cosine, about 2.6 times faster). Questions are embedded
on the CPU every time, so retrieval ms is what the app would see.

## Abilities and data

| | Ability | Data | Pass rule |
|---|---|---|---|
| A1 | recall one taught fact among many | 25 needle facts at 1k, 10k and 100k notes; LongMemEval single-session-user and single-session-assistant | every needed fact reached the context |
| A2 | join two facts | LongMemEval multi-session | every evidence session reached the context |
| A3 | knowledge update | LongMemEval knowledge-update; CAMR office-floor probe (+2 extra) | the newest value reached the context, and if a superseded value is there too, the two can be told apart (both dated and the newest later, or the newest says it is an update) |
| A4 | temporal | LongMemEval temporal-reasoning; CAMR electrician probe (+1 extra) | every needed fact reached the context in a note that shows its date, and no note from outside the period asked about did (the app's prompt does not give the model today's date, so the model cannot drop it) |
| A5 | counting | CAMR running log with 7, 30 and 100 runs | every run reached the context |
| A6 | implicit preference | LongMemEval single-session-preference; CAMR vegetarian probe (+2 extra) | the preference reached the context |
| A7 | abstention | LongMemEval abstention questions (ids ending `_abs`); "What is my blood type?" (+3 extra) | memory abstained |
| A8 | forget and privacy | PIN-hint probe on the real app (BGE); the app's forget and privacy tests (`tests/test_app*.py`) | each check holds |
| A9 | scale | the needle stores at 1k, 10k, 100k notes, each built and queried in its own process | peak RSS ≤ 8 GB, p95 retrieval ≤ 500 ms, needle recall no more than 10 points below the 1k store |
| A10 | do no harm (engine proxy) | general questions on a personal store; personal questions about people no note mentions, on the needle stores; A7's questions | nothing admitted; plus gate precision over all answerable and unanswerable questions |

Needed facts in LongMemEval are the turns flagged `has_answer` in each evidence session
(`answer_session_ids`); an evidence session with no flagged turn (94 of them in the S file, mostly
temporal-reasoning and abstention questions) counts as met when any of its turns reaches the context.
Each LongMemEval question gets a fresh store holding its whole chat history, oldest session first, one note
source per turn, written the way the app writes chat memory: `On <date> the user|assistant said: <turn>`.
Unlike the app, every turn is stored (questions and assistant replies too), so the bench measures the read
path rather than the app's choice of what to keep.

Every missed needed fact is given a reason, from where its best note was lost on the read path: *not
retrieved* (outside the vector and keyword hits), *similarity gate* (memory abstained: best note below 0.50),
*entity gate* (abstained because the question names something no eligible note mentions), *below margin*
(more than 0.15 under the best note), *budget full* (eligible, but the 384 tokens were used up).

### CAMR scenarios

Hand-written fixtures in `tests/fixtures/engine_bench/camr_scenarios.json`, clearly labelled there. Every
scenario store starts with 20 everyday personal notes (dentist, Wi-Fi, chama, car, ...), then the
scenario's notes are taught exactly as the app would: `teach(text)` for a note, `On <date> the user said:
<text>` for chat memory. The probes from the brief (office floor, electrician, running count,
vegetarian, blood type, PIN hint) are marked `from_brief`; the others are extra probes of the same kinds.
Today is taken as 2026-10-21.

### LongMemEval: source and licence

* Dataset: LongMemEval (Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu, "LongMemEval:
  Benchmarking Chat Assistants on Long-Term Interactive Memory", ICLR 2025, arXiv:2410.10813).
* Source: Hugging Face `xiaowu0162/longmemeval-cleaned`, revision
  `98d7416c24c778c2fee6e6f3006e7a073259d48f` (2025-09-19), the cleaned release that replaces the original
  (it removes history sessions that interfered with answer correctness).
* Licence: MIT. Checked on 2026-10-21: the dataset card declares `license: mit`, and the code repository
  (github.com/xiaowu0162/LongMemEval) carries an MIT LICENSE, "Copyright (c) 2024 Di Wu". The filler chat
  sessions inside the histories come from ShareGPT and UltraChat, as the paper describes.
* Files (downloaded by `engine_bench.py fetch`, checked by sha256, kept outside the repository in
  `$CAMR_BENCH_HOME/longmemeval/`; nothing of the dataset is committed except question texts and ids in
  `records/lme.jsonl`):
  * `longmemeval_s_cleaned.json` (used): sha256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`,
    500 questions, each with a history of about 50 sessions (about 115k tokens), mostly unrelated chat.
  * `longmemeval_oracle.json` (fetched, not scored: its histories hold only the evidence sessions, so it
    cannot test retrieval): sha256 `821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c`.
* Subsample: stratified by question type with seed 13, at most 40 per type, all 30 abstention questions:
  260 of 500 questions (single-session-user 40, single-session-assistant 40, multi-session 40,
  knowledge-update 40, temporal-reasoning 40, single-session-preference 30, abstention 30). Embedding every
  history of all 500 would take about 40 minutes on this machine; 260 keeps the whole run near an hour.
* Needle-store filler: the sampled questions' history sessions that are no question's evidence, shuffled
  with the same seed (10,627 sessions), cut to make exactly 1k, 10k or 100k notes with the 25 needles.

## Running it

```bash
PYTHONPATH=. python scripts/engine_bench.py all
```

Steps: `fetch` (download and check), `prepare` (subsample, filler), `embed` (resumable vector cache),
`run` (suites `camr`, `a8`, `lme`, `scale`; `--only lme` runs one; LongMemEval and scale skip what is already
scored), `report`. Large files go to `$CAMR_BENCH_HOME` (default `~/.cache/camr-bench`: about 0.5 GB of
data, 0.5 GB of vectors and 0.5 GB of needle stores), never into the repository. Everything stays under
8 GB of RAM: the largest process (prepare, which reads the 277 MB dataset) peaks near 1.6 GB.

BGE runs on at most 4 CPU threads (`CAMR_BENCH_THREADS`), since the bench shares the machine with training
jobs. 1M notes was not run: the store would take about 4.7 GB of disk (470 MB per 100k notes; this machine
has under 20 GB free) and about an hour of embedding, and the machine was busy with skill-card training.
`engine_bench.py run --only scale --scales 1000000` runs it later; until then the 10k and 100k numbers are
the trend to extrapolate.

## Baseline 2026-10-21

First full run: 260 LongMemEval questions, 23 CAMR probes, 75 needle and 36 absent-entity questions at three
sizes, 16 forget and privacy checks; about 45 minutes, of which 30 were embedding (the GPU was shared).
Full tables in `scorecard.md`.

| | Ability | Pass | Main reason for misses |
|---|---|---|---|
| A1 | recall one fact | 88% | holds to 10k notes (96%); 80% at 100k, where long chat chunks fill the budget |
| A2 | join two facts | 28% | budget full: 384 tokens hold about three chat chunks, so the second session rarely fits |
| A3 | knowledge update | 65% | the newest value misses the context in 30% of LongMemEval updates; the old value is there in 28 of 40 and ranks above the new one in 15 |
| A4 | temporal | 40% | budget full (as A2); the electrician probe fails because the September note shares the context and nothing tells the model today's date |
| A5 | counting | 1 of 3 | 7 runs pass; at 30 and 100 runs only 15 reach the context (about 16 short notes fill 384 tokens) |
| A6 | implicit preference | 70% | LongMemEval 73%, but the vegetarian probe fails: the entity gate takes "Friday" for a name and abstains ("Mombasa" too) |
| A7 | abstention | 15% | abstention questions score 0.55 to 0.80 top similarity, the same range as answerable ones (median 0.74), so the 0.50 gate opens; "What is my blood type?" does abstain |
| A8 | forget and privacy | 14 of 16 | forget leaves the lowercase word in the keyword index (`note_fts_data`): "kisumu" is still in the file after forgetting; personal questions made 0 web requests |
| A9 | scale | 2 of 3 | 100k fails only on recall (80% against 96% at 1k); p95 165 ms and 0.57 GB peak RSS are well within limits |
| A10 | do no harm | 62% | general and absent-entity questions get an empty context (46 of 48); the misses are A7's questions; gate precision 91%, specificity 62% |

The gaps expected before the run were A3, A4, A5 beyond about 16 notes, and A6. They are all there. Two
were not expected: abstention (A7) and joining facts (A2). One check failed that the app's tests
pass: forget leaves its words in the keyword index (the app test looks for the original-case text only).
Running `INSERT INTO note_fts(note_fts) VALUES('optimize')` after a delete clears it; that is Phase 2.

Where the misses come from, over every needed fact that did not reach the context: *budget full*
dominates (31 of A2's 46 misses, 33 of A4's 44). Then *not retrieved* (counting past k, multi-session).
Then the *entity gate* (A6 probes, A1 "Samsung TV"). *Below margin* is a small share. Retrieval is rarely
the problem at these sizes; what the 384-token budget can hold and the gate are.

Caveats: the CAMR probe sets are small (1 to 3 questions per ability) and say *what* fails, not how often.
The LongMemEval sample is 30 to 40 per type, so intervals are about ±15 points. All of this is the read
path only: a small model reading these contexts may still answer wrongly (or rightly by its own knowledge).
