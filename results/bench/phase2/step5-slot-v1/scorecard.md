# CAMR engine bench: scorecard

Generated 2026-10-22T00:02:40+00:00 from commit `82ccc5c-dirty` by `scripts/engine_bench.py` (records in `results/bench/records/`). Model-free: each question is scored from what CAMR Personal's read path admitted into the context. Machine: arm64 Darwin 27.0.0, 10 CPUs.

## Per ability

| | Ability | n | Pass (95% CI) | All-needed recall | Distractor share | Context tokens | Retrieval ms p50 / p95 | Abstained |
|---|---|---|---|---|---|---|---|---|
| A1 | recall one taught fact among many | 155 | 87% (81–91) | 87% | 79% | 303 | 15.6 / 138.3 | 4% |
| A2 | join two facts | 40 | 38% (24–53) | 38% | 71% | 430 | 10.0 / 15.2 | 0% |
| A3 | knowledge update | 43 | 70% (55–81) | 70% | 84% | 358 | 11.9 / 72.0 | 5% |
| A4 | temporal | 42 | 48% (33–62) | 52% | 76% | 399 | 9.8 / 12.7 | 0% |
| A5 | counting | 3 | 67% (21–94) | 67% | 27% | 585 | 7.2 / 7.6 | 0% |
| A6 | implicit preference | 33 | 79% (62–89) | 79% | 85% | 347 | 10.5 / 12.8 | 9% |
| A7 | abstention | 34 | 29% (17–46) | – | 88% | 367 | 9.2 / 17.5 | 29% |
| A8 | forget and privacy | 16 | 100% (81–100) | – | – | – | – / – | – |
| A9 | scale | 3 | 100% (44–100) | – | – | – | 15.2 / 75.0 | – |
| A10 | do no harm (engine proxy) | 82 | 68% (58–77) | – | 80% | 185 | 12.2 / 71.7 | 68% |

Pass rules (camr/eval/abilities.py): A1, A2, A5, A6 every needed fact reached the context; A3 the newest value did, and a superseded value next to it can be told apart (dates, or the newest says it is an update); A4 every needed fact did in a note that shows its date, and nothing from outside the period asked about (the app's prompt does not give the model today's date); A7 memory abstained; A8 each forget or privacy check held; A9 peak RSS <= 8192 MB, p95 retrieval <= 500 ms, needle recall no more than 10% below the 1k store; A10 nothing was admitted for a question memory has nothing for (A7's questions included).

## By suite

| Ability | Suite | n | Pass | All-needed | Distractor | Tokens | ms p50 / p95 | Abstained | Why needed facts were missed |
|---|---|---|---|---|---|---|---|---|---|
| A1 | lme-ssa | 40 | 82% | 82% | 62% | 372 | 15.5 / 19.5 | 0% | budget full 5, below margin 1, not retrieved 1 |
| A1 | lme-ssu | 40 | 85% | 85% | 81% | 366 | 9.2 / 11.6 | 5% | budget full 3, entity gate 2, below margin 1 |
| A1 | needle-100k | 25 | 84% | 84% | 89% | 275 | 91.1 / 193.9 | 4% | budget full 3, entity gate 1 |
| A1 | needle-10k | 25 | 96% | 96% | 86% | 246 | 31.6 / 44.7 | 4% | entity gate 1 |
| A1 | needle-1k | 25 | 92% | 92% | 84% | 178 | 13.3 / 21.6 | 8% | entity gate 2 |
| A2 | lme-ms | 40 | 38% | 38% | 71% | 430 | 10.0 / 15.2 | 0% | budget full 24, below margin 7, not retrieved 7 |
| A3 | camr-brief | 1 | 100% | 100% | 51% | 37 | 7.0 / 7.0 | 0% | – |
| A3 | camr-extra | 2 | 100% | 100% | 47% | 45 | 6.5 / 6.7 | 0% | – |
| A3 | lme-ku | 40 | 68% | 68% | 87% | 382 | 12.0 / 72.0 | 5% | budget full 7, below margin 4, entity gate 2 |
| A4 | camr-brief | 1 | 100% | 100% | 0% | 22 | 7.1 / 7.1 | 0% | – |
| A4 | camr-extra | 1 | 100% | 100% | 93% | 351 | 6.8 / 6.8 | 0% | – |
| A4 | lme-tr | 40 | 45% | 50% | 77% | 409 | 9.8 / 12.7 | 0% | budget full 27, not retrieved 8, below margin 2 |
| A5 | camr-count-100 | 1 | 0% | 0% | 2% | 1017 | 7.6 / 7.6 | 0% | budget full 25 |
| A5 | camr-count-30 | 1 | 100% | 100% | 11% | 447 | 7.0 / 7.0 | 0% | – |
| A5 | camr-count-7 | 1 | 100% | 100% | 68% | 290 | 7.2 / 7.2 | 0% | – |
| A6 | camr-brief | 1 | 100% | 100% | 89% | 170 | 6.8 / 6.8 | 0% | – |
| A6 | camr-extra | 2 | 100% | 100% | 42% | 155 | 6.5 / 6.5 | 50% | – |
| A6 | lme-ssp | 30 | 77% | 77% | 87% | 366 | 10.5 / 12.8 | 7% | budget full 5, entity gate 2 |
| A7 | camr-brief | 1 | 100% | – | 0% | 0 | 5.8 / 5.8 | 100% | – |
| A7 | camr-extra | 3 | 100% | – | 0% | 0 | 6.0 / 6.0 | 100% | – |
| A7 | lme-abs | 30 | 20% | – | 100% | 416 | 9.4 / 17.5 | 20% | – |
| A8 | app-tests | 9 | 100% | – | – | – | – / – | – | – |
| A8 | forget | 5 | 100% | – | – | – | – / – | – | – |
| A8 | privacy | 2 | 100% | – | – | – | – / – | – | – |
| A9 | scale-100k | 1 | 100% | – | – | – | 75.0 / 75.0 | – | – |
| A9 | scale-10k | 1 | 100% | – | – | – | 15.2 / 15.2 | – | – |
| A9 | scale-1k | 1 | 100% | – | – | – | 14.4 / 14.4 | – | – |
| A10 | A7 camr-brief | 1 | 100% | – | 0% | 0 | 5.8 / 5.8 | 100% | – |
| A10 | A7 camr-extra | 3 | 100% | – | 0% | 0 | 6.0 / 6.0 | 100% | – |
| A10 | A7 lme-abs | 30 | 20% | – | 100% | 416 | 9.4 / 17.5 | 20% | – |
| A10 | absent-100k | 12 | 83% | – | 100% | 108 | 66.5 / 93.4 | 83% | – |
| A10 | absent-10k | 12 | 100% | – | 100% | 58 | 19.2 / 31.9 | 100% | – |
| A10 | absent-1k | 12 | 100% | – | 100% | 59 | 15.5 / 20.3 | 100% | – |
| A10 | general-on-personal | 12 | 100% | – | 0% | 0 | 5.7 / 6.6 | 100% | – |

## CAMR probes

From the brief unless marked *extra*. Context = what reached the model, with each note's similarity.

| Probe | Ability | Question | Pass | Context |
|---|---|---|---|---|
| office-floor | A3 | Which floor is my office on? | yes | [0.767] - [2026-10-21] My office is on the 3rd floor of Delta House.; [0.737] - [2026-10-21] Update: my office moved to the 5th floor. |
| gp-switch *extra* | A3 | Who is my GP? | yes | [0.709] - [2026-03-04] The user said: My GP is Dr. Otieno at the Avenue clinic.; [0.63] - [2026-09-18] The user said: I changed GPs, I now see Dr. Chebet at Nairobi West clinic. |
| gym-fee *extra* | A3 | How much is the gym membership each month? | yes | [0.755] - [2026-10-21] The gym membership costs 4,500 shillings a month.; [0.739] - [2026-10-21] The gym membership costs 5,200 shillings a month from October. |
| electrician | A4 | What did the electrician fix last week? | yes | [0.71] - [2026-10-13] The user said: The electrician came today and fixed the kitchen socket. |
| haircut *extra* | A4 | Where did I get my hair cut this month? | yes | 12 notes; [0.612] - [2026-10-17] The user said: Got a haircut at the; [0.525] - [2026-10-21] Dentist: Dentist appointment moved ; [0.548] - [2026-10-21] Mum's birthday: Mum's birthday is o … |
| vegetarian | A6 | Can you suggest a dinner place for Friday? | yes | 6 notes; [0.373] - [about the user] I am vegetarian and I don't eat; [0.484] - [2026-10-21] Mum's birthday: Mum's birthday is o; [0.479] - [2026-10-21] Book club: The book club is reading … |
| fear-of-flying *extra* | A6 | What's the best way to get to Mombasa next month? | yes | [0.366] - [about the user] I get very anxious on planes and avoid flying whenever I can. |
| lactose *extra* | A6 | Any ideas for a quick breakfast before work? | yes | 10 notes; [0.501] - [about the user] Milk upsets my stomach, I think; [0.517] - [2026-07-22] The user said: Milk upsets my stoma; [0.429] - [2026-10-21] Dentist: Dentist appointment moved  … |
| blood-type | A7 | What is my blood type? | yes | (abstained) |
| unknown-personal *extra* | A7 | What is my passport number? | yes | (abstained) |
| unknown-personal *extra* | A7 | When is my brother's wedding? | yes | (abstained) |
| unknown-personal *extra* | A7 | What is the registration number of my motorbike? | yes | (abstained) |
| running-count | A5 | How many times did I go running this month? | yes | 7 of 7 reached; 16 notes; [0.579] - [2026-10-02] I went running before work; [0.559] - [2026-10-05] I went running in the rain; [0.566] - [2026-10-08] I went running with Kamau … |
| running-count *extra* | A5 | How many times have I gone running in total? | yes | 30 of 30 reached; 32 notes; [0.573] - [2026-08-23] I went running before work; [0.545] - [2026-08-25] I went running in the rain; [0.529] - [2026-08-27] I went running with Kamau … |
| running-count *extra* | A5 | How many times have I gone running in total? | no (budget full) | 75 of 100 reached; 76 notes; [0.581] - [2026-04-05] I went running before work; [0.552] - [2026-04-07] I went running in the rain; [0.562] - [2026-04-11] I went running after lunch … |

## A8 forget and privacy

| Check | Pass | Detail |
|---|---|---|
| forget: rows | yes | 1 note(s) removed; rows left {'note': 0, 'source': 0, 'rejection': 0, 'note_embedding': 0, 'note_vec': 0}; before forgetting the file held 3 trace(s) |
| forget: keyword index | yes | 0 keyword hit(s) for 'kisumu' |
| forget: file bytes | yes | no trace in the file |
| forget: recall | yes | 0 note(s) admitted, 0 about it |
| forget: said in chat, then chat deleted | yes | after forget only: ['memory.sqlite:Kisumu', 'memory.sqlite:PIN hint']; after deleting the chat too: none |
| privacy: personal questions stay local | yes | 0 web request(s) for 8 personal questions |
| privacy: control (a general question is looked up) | yes | 8 request(s) for 'Who directed The Loudwater Mystery?' |
| unit test: test_forget_removes_notes_and_vectors | yes | PASSED |
| unit test: test_teaching_an_edited_file_replaces_the_old_version | yes | PASSED |
| unit test: test_thumbs_down_takes_back_an_approval | yes | PASSED |
| unit test: test_a_personal_question_is_never_looked_up_and_asks_to_be_taught | yes | PASSED |
| unit test: test_what_counts_as_a_question_about_the_user | yes | PASSED |
| unit test: test_personal_questions_without_a_pronoun_never_leave_the_machine | yes | PASSED |
| unit test: test_a_name_only_the_users_notes_mention_is_never_sent | yes | PASSED |
| unit test: test_learning_online_can_be_turned_off | yes | PASSED |
| unit test: test_refuses_foreign_hosts_and_cross_site_posts | yes | PASSED |

## A9 scale

Needle questions (A1) and absent-entity questions (A10) on stores of LongMemEval chat turns plus 25 taught facts. Each size is built and queried in its own process; peak RSS includes the BGE model (about 0.5 GB).

| Notes | Store MB | Build s | Peak RSS build MB | Peak RSS query MB | Retrieval ms p50 / p95 | Needle recall | Pass |
|---|---|---|---|---|---|---|---|
| 1018 | 5.0 | 9.1 | 531.1 | 557.5 | 14.44 / 24.11 | 92% | yes |
| 10107 | 47.8 | 38.1 | 516.7 | 400.9 | 15.19 / 33.51 | 96% | yes |
| 101135 | 474.9 | 324.4 | 483.1 | 561.7 | 74.96 / 177.22 | 84% | yes |

1M notes was not run: the store would need about 4.7 GB of disk (470 MB per 100k notes) and about an hour of embedding, and the machine was shared with a training job; the 10k → 100k trend above is what to extrapolate from (`engine_bench.py run --only scale --scales 1000000`).

## A10 gate

Over 316 answerable and 82 unanswerable questions: the gate let memory through for 305 answerable and 26 unanswerable ones. Precision 92%, specificity 68%, sensitivity 97%.

## Setup

* Read path: write_policy verbatim, chunk_tokens 120, chunk_overlap 16, retrieval_policy similarity_only, k 20, keyword_k 20, token_budget 384, min_similarity 0.5, similarity_margin 0.15, entity_gate True, expansion entity, packing greedy_stop, embedder BAAI/bge-small-en-v1.5, vector_backend sqlite-vec, dated_context True, time_filter True, entity_gate_skip_time True, profile True, profile_budget 64, profile_min_similarity -1.0, aggregate True, aggregate_k 100, aggregate_budget 1024, compress none, slot_gate True, chunk_tokens_used 120.
* LongMemEval: `longmemeval_s_cleaned.json` from `xiaowu0162/longmemeval-cleaned` at revision `98d7416c24c7` (sha256 `d6f21ea9d60a0d56…`), MIT licence. Stratified subsample, seed 13, at most 40 per question type: 260 of 500 questions (single-session-user 40, abstention 30, multi-session 40, single-session-preference 30, temporal-reasoning 40, knowledge-update 40, single-session-assistant 40).
* Each LongMemEval question gets a fresh store holding its whole chat history, one note source per turn ('On <date> the user|assistant said: …'); needed facts are the turns flagged has_answer in each evidence session (every turn of an evidence session that has no flag).
* Passage vectors computed once on mps and cached; questions embedded on the CPU each time (retrieval ms is what the app would see).
