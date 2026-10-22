# CAMR engine bench: scorecard

Generated 2026-10-21T23:52:02+00:00 from commit `82ccc5c-dirty` by `scripts/engine_bench.py` (records in `results/bench/records/`). Model-free: each question is scored from what CAMR Personal's read path admitted into the context. Machine: arm64 Darwin 27.0.0, 10 CPUs.

## Per ability

| | Ability | n | Pass (95% CI) | All-needed recall | Distractor share | Context tokens | Retrieval ms p50 / p95 | Abstained |
|---|---|---|---|---|---|---|---|---|
| A1 | recall one taught fact among many | 155 | 91% (85–95) | 91% | 83% | 304 | 12.2 / 81.2 | 3% |
| A2 | join two facts | 40 | 52% (38–67) | 52% | 72% | 440 | 10.6 / 15.3 | 0% |
| A3 | knowledge update | 43 | 81% (67–90) | 81% | 86% | 381 | 9.6 / 12.2 | 5% |
| A4 | temporal | 42 | 67% (52–79) | 71% | 75% | 412 | 10.0 / 12.6 | 0% |
| A5 | counting | 3 | 67% (21–94) | 67% | 27% | 585 | 7.0 / 8.0 | 0% |
| A6 | implicit preference | 33 | 85% (69–93) | 85% | 84% | 382 | 10.9 / 14.9 | 6% |
| A7 | abstention | 34 | 12% (5–27) | – | 97% | 443 | 9.6 / 12.3 | 12% |
| A8 | forget and privacy | 16 | 100% (81–100) | – | – | – | – / – | – |
| A9 | scale | 3 | 100% (44–100) | – | – | – | 12.3 / 65.4 | – |
| A10 | do no harm (engine proxy) | 82 | 61% (50–71) | – | 84% | 218 | 9.6 / 61.0 | 61% |

Pass rules (camr/eval/abilities.py): A1, A2, A5, A6 every needed fact reached the context; A3 the newest value did, and a superseded value next to it can be told apart (dates, or the newest says it is an update); A4 every needed fact did in a note that shows its date, and nothing from outside the period asked about (the app's prompt does not give the model today's date); A7 memory abstained; A8 each forget or privacy check held; A9 peak RSS <= 8192 MB, p95 retrieval <= 500 ms, needle recall no more than 10% below the 1k store; A10 nothing was admitted for a question memory has nothing for (A7's questions included).

## By suite

| Ability | Suite | n | Pass | All-needed | Distractor | Tokens | ms p50 / p95 | Abstained | Why needed facts were missed |
|---|---|---|---|---|---|---|---|---|---|
| A1 | lme-ssa | 40 | 82% | 82% | 73% | 361 | 12.8 / 14.1 | 0% | budget full 5, below margin 1, not retrieved 1 |
| A1 | lme-ssu | 40 | 90% | 90% | 87% | 389 | 9.7 / 11.0 | 2% | budget full 2, below margin 1, entity gate 1 |
| A1 | needle-100k | 25 | 96% | 96% | 89% | 291 | 76.8 / 111.7 | 4% | entity gate 1 |
| A1 | needle-10k | 25 | 96% | 96% | 86% | 233 | 12.5 / 14.7 | 4% | entity gate 1 |
| A1 | needle-1k | 25 | 96% | 96% | 81% | 161 | 7.0 / 7.6 | 4% | entity gate 1 |
| A2 | lme-ms | 40 | 52% | 52% | 72% | 440 | 10.6 / 15.3 | 0% | budget full 16, below margin 7, not retrieved 7 |
| A3 | camr-brief | 1 | 100% | 100% | 51% | 37 | 7.5 / 7.5 | 0% | – |
| A3 | camr-extra | 2 | 100% | 100% | 47% | 45 | 6.6 / 6.6 | 0% | – |
| A3 | lme-ku | 40 | 80% | 80% | 89% | 406 | 9.6 / 12.2 | 5% | below margin 4, entity gate 2, budget full 2 |
| A4 | camr-brief | 1 | 100% | 100% | 0% | 22 | 7.0 / 7.0 | 0% | – |
| A4 | camr-extra | 1 | 100% | 100% | 93% | 351 | 6.8 / 6.8 | 0% | – |
| A4 | lme-tr | 40 | 65% | 70% | 76% | 423 | 10.2 / 12.6 | 0% | budget full 11, not retrieved 8, below margin 2 |
| A5 | camr-count-100 | 1 | 0% | 0% | 2% | 1017 | 8.0 / 8.0 | 0% | budget full 25 |
| A5 | camr-count-30 | 1 | 100% | 100% | 11% | 447 | 7.0 / 7.0 | 0% | – |
| A5 | camr-count-7 | 1 | 100% | 100% | 68% | 290 | 6.7 / 6.7 | 0% | – |
| A6 | camr-brief | 1 | 100% | 100% | 89% | 170 | 6.5 / 6.5 | 0% | – |
| A6 | camr-extra | 2 | 100% | 100% | 42% | 155 | 6.6 / 7.0 | 50% | – |
| A6 | lme-ssp | 30 | 83% | 83% | 87% | 404 | 11.0 / 14.9 | 3% | budget full 4, entity gate 1 |
| A7 | camr-brief | 1 | 100% | – | 0% | 0 | 6.0 / 6.0 | 100% | – |
| A7 | camr-extra | 3 | 0% | – | 100% | 356 | 6.3 / 6.4 | 0% | – |
| A7 | lme-abs | 30 | 10% | – | 100% | 466 | 9.8 / 12.3 | 10% | – |
| A8 | app-tests | 9 | 100% | – | – | – | – / – | – | – |
| A8 | forget | 5 | 100% | – | – | – | – / – | – | – |
| A8 | privacy | 2 | 100% | – | – | – | – / – | – | – |
| A9 | scale-100k | 1 | 100% | – | – | – | 65.4 / 65.4 | – | – |
| A9 | scale-10k | 1 | 100% | – | – | – | 12.3 / 12.3 | – | – |
| A9 | scale-1k | 1 | 100% | – | – | – | 6.7 / 6.7 | – | – |
| A10 | A7 camr-brief | 1 | 100% | – | 0% | 0 | 6.0 / 6.0 | 100% | – |
| A10 | A7 camr-extra | 3 | 0% | – | 100% | 356 | 6.3 / 6.4 | 0% | – |
| A10 | A7 lme-abs | 30 | 10% | – | 100% | 466 | 9.8 / 12.3 | 10% | – |
| A10 | absent-100k | 12 | 83% | – | 100% | 114 | 57.9 / 75.5 | 83% | – |
| A10 | absent-10k | 12 | 100% | – | 100% | 58 | 12.0 / 15.0 | 100% | – |
| A10 | absent-1k | 12 | 100% | – | 100% | 59 | 6.8 / 7.0 | 100% | – |
| A10 | general-on-personal | 12 | 100% | – | 0% | 0 | 5.9 / 6.3 | 100% | – |

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
| unknown-personal *extra* | A7 | What is my passport number? | no | 12 notes; [0.425] - [2026-10-21] Dentist: Dentist appointment moved ; [0.512] - [2026-10-21] Wi-Fi: The home router admin page i; [0.452] - [2026-10-21] Project CAMR: Project CAMR supervis … |
| unknown-personal *extra* | A7 | When is my brother's wedding? | no | 11 notes; [0.498] - [2026-10-21] Dentist: Dentist appointment moved ; [0.436] - [2026-10-21] Wi-Fi: The home router admin page i; [0.575] - [2026-10-21] Project CAMR: Project CAMR supervis … |
| unknown-personal *extra* | A7 | What is the registration number of my motorbike? | no | 12 notes; [0.452] - [2026-10-21] Dentist: Dentist appointment moved ; [0.484] - [2026-10-21] Wi-Fi: The home router admin page i; [0.504] - [2026-10-21] Project CAMR: Project CAMR supervis … |
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
| 1018 | 5.0 | 9.1 | 531.1 | 580.0 | 6.74 / 7.53 | 96% | yes |
| 10107 | 47.8 | 38.1 | 516.7 | 595.6 | 12.32 / 14.74 | 96% | yes |
| 101135 | 474.9 | 324.4 | 483.1 | 591.2 | 65.44 / 104.53 | 96% | yes |

1M notes was not run: the store would need about 4.7 GB of disk (470 MB per 100k notes) and about an hour of embedding, and the machine was shared with a training job; the 10k → 100k trend above is what to extrapolate from (`engine_bench.py run --only scale --scales 1000000`).

## A10 gate

Over 316 answerable and 82 unanswerable questions: the gate let memory through for 308 answerable and 32 unanswerable ones. Precision 91%, specificity 61%, sensitivity 97%.

## Setup

* Read path: write_policy verbatim, chunk_tokens 120, chunk_overlap 16, retrieval_policy similarity_only, k 20, keyword_k 20, token_budget 384, min_similarity 0.5, similarity_margin 0.15, entity_gate True, expansion entity, packing greedy_stop, embedder BAAI/bge-small-en-v1.5, vector_backend sqlite-vec, dated_context True, time_filter True, entity_gate_skip_time True, profile True, profile_budget 64, profile_min_similarity -1.0, aggregate True, aggregate_k 100, aggregate_budget 1024, compress sentences, slot_gate False, chunk_tokens_used 120.
* LongMemEval: `longmemeval_s_cleaned.json` from `xiaowu0162/longmemeval-cleaned` at revision `98d7416c24c7` (sha256 `d6f21ea9d60a0d56…`), MIT licence. Stratified subsample, seed 13, at most 40 per question type: 260 of 500 questions (single-session-user 40, abstention 30, multi-session 40, single-session-preference 30, temporal-reasoning 40, knowledge-update 40, single-session-assistant 40).
* Each LongMemEval question gets a fresh store holding its whole chat history, one note source per turn ('On <date> the user|assistant said: …'); needed facts are the turns flagged has_answer in each evidence session (every turn of an evidence session that has no flag).
* Passage vectors computed once on mps and cached; questions embedded on the CPU each time (retrieval ms is what the app would see).
