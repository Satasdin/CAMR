# CAMR engine bench: scorecard

Generated 2026-10-22T01:49:45+00:00 from commit `008e72d-dirty` by `scripts/engine_bench.py` (records in `results/bench/records/`). Model-free: each question is scored from what CAMR Personal's read path admitted into the context. Machine: arm64 Darwin 27.0.0, 10 CPUs.

## Per ability

| | Ability | n | Pass (95% CI) | All-needed recall | Distractor share | Context tokens | Retrieval ms p50 / p95 | Abstained |
|---|---|---|---|---|---|---|---|---|
| A1 | recall one taught fact among many | 180 | 87% (81–91) | 87% | 62% | 248 | 23.0 / 9523.0 | 3% |
| A2 | join two facts | 40 | 28% (16–43) | 28% | 69% | 334 | 21.2 / 60.0 | 0% |
| A3 | knowledge update | 43 | 65% (50–78) | 72% | 77% | 291 | 15.5 / 28.2 | 5% |
| A4 | temporal | 42 | 40% (27–56) | 45% | 71% | 319 | 19.8 / 34.6 | 2% |
| A5 | counting | 3 | 33% (6–79) | 33% | 23% | 372 | 9.7 / 10.4 | 0% |
| A6 | implicit preference | 33 | 70% (53–83) | 70% | 76% | 294 | 20.0 / 38.4 | 12% |
| A7 | abstention | 34 | 15% (6–30) | – | 85% | 286 | 17.5 / 41.1 | 15% |
| A8 | forget and privacy | 16 | 88% (64–96) | – | – | – | – / – | – |
| A9 | scale | 4 | 50% (15–85) | – | – | – | 23.1 / 8123.8 | – |
| A10 | do no harm (engine proxy) | 94 | 64% (54–73) | – | 36% | 121 | 19.3 / 8558.8 | 64% |

Pass rules (camr/eval/abilities.py): A1, A2, A5, A6 every needed fact reached the context; A3 the newest value did, and a superseded value next to it can be told apart (dates, or the newest says it is an update); A4 every needed fact did in a note that shows its date, and nothing from outside the period asked about (the app's prompt does not give the model today's date); A7 memory abstained; A8 each forget or privacy check held; A9 peak RSS <= 8192 MB, p95 retrieval <= 500 ms, needle recall no more than 10% below the 1k store; A10 nothing was admitted for a question memory has nothing for (A7's questions included).

## By suite

| Ability | Suite | n | Pass | All-needed | Distractor | Tokens | ms p50 / p95 | Abstained | Why needed facts were missed |
|---|---|---|---|---|---|---|---|---|---|
| A1 | lme-ssa | 40 | 82% | 82% | 54% | 307 | 19.2 / 28.8 | 0% | budget full 5, below margin 1, not retrieved 1 |
| A1 | lme-ssu | 40 | 90% | 90% | 77% | 319 | 19.4 / 46.9 | 2% | budget full 2, below margin 1, entity gate 1 |
| A1 | needle-100k | 25 | 80% | 80% | 65% | 226 | 108.9 / 184.5 | 4% | budget full 4, entity gate 1 |
| A1 | needle-10k | 25 | 96% | 96% | 57% | 199 | 23.6 / 36.0 | 4% | entity gate 1 |
| A1 | needle-1M | 25 | 76% | 76% | 74% | 249 | 8123.8 / 13844.7 | 4% | budget full 3, below margin 1, not retrieved 1, entity gate 1 |
| A1 | needle-1k | 25 | 96% | 96% | 42% | 109 | 9.2 / 10.6 | 4% | entity gate 1 |
| A2 | lme-ms | 40 | 28% | 28% | 69% | 334 | 21.2 / 60.0 | 0% | budget full 31, not retrieved 9, below margin 6 |
| A3 | camr-brief | 1 | 100% | 100% | 52% | 23 | 14.2 / 14.2 | 0% | – |
| A3 | camr-extra | 2 | 50% | 100% | 46% | 37 | 12.4 / 14.5 | 0% | – |
| A3 | lme-ku | 40 | 65% | 70% | 79% | 310 | 15.7 / 28.2 | 5% | budget full 6, below margin 4, entity gate 2 |
| A4 | camr-brief | 1 | 0% | 100% | 46% | 39 | 11.3 / 11.3 | 0% | – |
| A4 | camr-extra | 1 | 0% | 100% | 92% | 293 | 13.6 / 13.6 | 0% | – |
| A4 | lme-tr | 40 | 42% | 42% | 71% | 327 | 19.9 / 34.6 | 2% | budget full 33, not retrieved 8, entity gate 2, below margin 1 |
| A5 | camr-count-100 | 1 | 0% | 0% | 6% | 367 | 9.4 / 9.4 | 0% | not retrieved 69, budget full 16 |
| A5 | camr-count-30 | 1 | 0% | 0% | 6% | 372 | 9.7 / 9.7 | 0% | budget full 9, not retrieved 6 |
| A5 | camr-count-7 | 1 | 100% | 100% | 56% | 377 | 10.4 / 10.4 | 0% | – |
| A6 | camr-brief | 1 | 0% | 0% | 0% | 0 | 11.7 / 11.7 | 100% | entity gate 1 |
| A6 | camr-extra | 2 | 50% | 50% | 44% | 108 | 9.9 / 10.5 | 50% | entity gate 1 |
| A6 | lme-ssp | 30 | 73% | 73% | 81% | 316 | 20.3 / 38.4 | 7% | budget full 6, entity gate 2 |
| A7 | camr-brief | 1 | 100% | – | 0% | 0 | 10.1 / 10.1 | 100% | – |
| A7 | camr-extra | 3 | 0% | – | 100% | 305 | 9.2 / 9.5 | 0% | – |
| A7 | lme-abs | 30 | 13% | – | 87% | 294 | 18.1 / 41.1 | 13% | – |
| A8 | app-tests | 9 | 100% | – | – | – | – / – | – | – |
| A8 | forget | 5 | 60% | – | – | – | – / – | – | – |
| A8 | privacy | 2 | 100% | – | – | – | – / – | – | – |
| A9 | scale-100k | 1 | 0% | – | – | – | 98.7 / 98.7 | – | – |
| A9 | scale-10k | 1 | 100% | – | – | – | 23.1 / 23.1 | – | – |
| A9 | scale-1M | 1 | 0% | – | – | – | 8123.8 / 8123.8 | – | – |
| A9 | scale-1k | 1 | 100% | – | – | – | 9.4 / 9.4 | – | – |
| A10 | A7 camr-brief | 1 | 100% | – | 0% | 0 | 10.1 / 10.1 | 100% | – |
| A10 | A7 camr-extra | 3 | 0% | – | 100% | 305 | 9.2 / 9.5 | 0% | – |
| A10 | A7 lme-abs | 30 | 13% | – | 87% | 294 | 18.1 / 41.1 | 13% | – |
| A10 | absent-100k | 12 | 83% | – | 17% | 53 | 96.0 / 137.4 | 83% | – |
| A10 | absent-10k | 12 | 100% | – | 0% | 0 | 21.3 / 27.5 | 100% | – |
| A10 | absent-1M | 12 | 75% | – | 25% | 86 | 8006.3 / 13053.6 | 75% | – |
| A10 | absent-1k | 12 | 100% | – | 0% | 0 | 9.7 / 12.3 | 100% | – |
| A10 | general-on-personal | 12 | 100% | – | 0% | 0 | 12.5 / 22.6 | 100% | – |

## CAMR probes

From the brief unless marked *extra*. Context = what reached the model, with each note's similarity.

| Probe | Ability | Question | Pass | Context |
|---|---|---|---|---|
| office-floor | A3 | Which floor is my office on? | yes | [0.767] My office is on the 3rd floor of Delta House.; [0.737] Update: my office moved to the 5th floor. |
| gp-switch *extra* | A3 | Who is my GP? | yes | [0.709] On 2026-03-04 the user said: My GP is Dr. Otieno at the Avenue clinic.; [0.63] On 2026-09-18 the user said: I changed GPs, I now see Dr. Chebet at Nairobi West clinic. |
| gym-fee *extra* | A3 | How much is the gym membership each month? | no | [0.755] The gym membership costs 4,500 shillings a month.; [0.739] The gym membership costs 5,200 shillings a month from October. |
| electrician | A4 | What did the electrician fix last week? | no | [0.71] On 2026-10-13 the user said: The electrician came today and fixed the kitchen socket.; [0.701] On 2026-09-02 the user said: The electrician fixed the bathroom light. |
| haircut *extra* | A4 | Where did I get my hair cut this month? | no | 13 notes; [0.614] On 2026-08-09 the user said: Got a haircut at Kiny; [0.612] On 2026-10-17 the user said: Got a haircut at the ; [0.511] Running shoes: My running shoes are Asics Gel-Nimb … |
| vegetarian | A6 | Can you suggest a dinner place for Friday? | no (entity gate) | (abstained) |
| fear-of-flying *extra* | A6 | What's the best way to get to Mombasa next month? | no (entity gate) | (abstained) |
| lactose *extra* | A6 | Any ideas for a quick breakfast before work? | yes | 9 notes; [0.57] Lunch: Kevin at work recommended Mama Oliech's res; [0.517] On 2026-07-22 the user said: Milk upsets my stomac; [0.469] Book club: The book club is reading Dust by Yvonne … |
| blood-type | A7 | What is my blood type? | yes | (abstained) |
| unknown-personal *extra* | A7 | What is my passport number? | no | 14 notes; [0.455] Chama: The family chama meets on the last Sunday o; [0.546] Mum's birthday: Mum's birthday is on 17 November. ; [0.43] Running shoes: My running shoes are Asics Gel-Nimb … |
| unknown-personal *extra* | A7 | When is my brother's wedding? | no | 11 notes; [0.575] Project CAMR: Project CAMR supervisor meeting ever; [0.464] Chama: The family chama meets on the last Sunday o; [0.544] Mum's birthday: Mum's birthday is on 17 November.  … |
| unknown-personal *extra* | A7 | What is the registration number of my motorbike? | no | 14 notes; [0.47] Running shoes: My running shoes are Asics Gel-Nimb; [0.534] Cooking gas: The cooking gas cylinder is a 13 kg P; [0.44] Chama: The family chama meets on the last Sunday o … |
| running-count | A5 | How many times did I go running this month? | yes | 7 of 7 reached; 16 notes; [0.59] Running shoes: My running shoes are Asics Gel-Nimb; [0.527] Chama: The family chama meets on the last Sunday o; [0.579] On 2026-10-02 the user said: I went running before … |
| running-count *extra* | A5 | How many times have I gone running in total? | no (budget full, not retrieved) | 15 of 30 reached; 16 notes; [0.606] Running shoes: My running shoes are Asics Gel-Nimb; [0.588] On 2026-09-10 the user said: I went running after ; [0.586] On 2026-09-04 the user said: I went running before … |
| running-count *extra* | A5 | How many times have I gone running in total? | no (budget full, not retrieved) | 15 of 100 reached; 16 notes; [0.606] Running shoes: My running shoes are Asics Gel-Nimb; [0.589] On 2026-04-23 the user said: I went running after ; [0.588] On 2026-06-10 the user said: I went running after  … |

## A8 forget and privacy

| Check | Pass | Detail |
|---|---|---|
| forget: rows | yes | 1 note(s) removed; rows left {'note': 0, 'source': 0, 'rejection': 0, 'note_embedding': 0, 'note_vec': 0}; before forgetting the file held 3 trace(s) |
| forget: keyword index | yes | 0 keyword hit(s) for 'kisumu' |
| forget: file bytes | no | traces left: ['memory.sqlite:kisumu'] |
| forget: recall | yes | 0 note(s) admitted, 0 about it |
| forget: said in chat, then chat deleted | no | after forget only: ['memory.sqlite:Kisumu', 'memory.sqlite:kisumu', 'memory.sqlite:PIN hint']; after deleting the chat too: ['memory.sqlite:kisumu'] |
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
| 1002 | 4.9 | 3.4 | 522.7 | 546.8 | 9.37 / 10.56 | 96% | yes |
| 10000 | 47.5 | 9.2 | 539.5 | 507.5 | 23.05 / 36.0 | 96% | yes |
| 100001 | 470.1 | 131.8 | 567.9 | 525.8 | 98.65 / 165.21 | 80% | no |
| 1000004 | 4713.6 | 1099.7 | 588.6 | 567.5 | 8123.78 / 13777.99 | 76% | no |

The 1M store continues the S filler with LongMemEval M sessions (`prepare-m`). Its retrieval is disk-bound on this machine: sqlite-vec reads every vector, and the 4.7 GB store did not fit the page cache under the memory pressure of the time, so its latency is an upper bound; peak RSS stays near 0.6 GB.

## A10 gate

Over 341 answerable and 94 unanswerable questions: the gate let memory through for 329 answerable and 34 unanswerable ones. Precision 91%, specificity 64%, sensitivity 96%.

## Setup

* Read path: write_policy verbatim, chunk_tokens 120, chunk_overlap 16, retrieval_policy similarity_only, k 20, keyword_k 20, token_budget 384, min_similarity 0.5, similarity_margin 0.15, entity_gate True, expansion entity, packing greedy_stop, embedder BAAI/bge-small-en-v1.5, vector_backend sqlite-vec.
* LongMemEval: `longmemeval_s_cleaned.json` from `xiaowu0162/longmemeval-cleaned` at revision `98d7416c24c7` (sha256 `d6f21ea9d60a0d56…`), MIT licence. Stratified subsample, seed 13, at most 40 per question type: 260 of 500 questions (single-session-user 40, abstention 30, multi-session 40, single-session-preference 30, temporal-reasoning 40, knowledge-update 40, single-session-assistant 40).
* Each LongMemEval question gets a fresh store holding its whole chat history, one note source per turn ('On <date> the user|assistant said: …'); needed facts are the turns flagged has_answer in each evidence session (every turn of an evidence session that has no flag).
* Passage vectors computed once on mps and cached; questions embedded on the CPU each time (retrieval ms is what the app would see).
