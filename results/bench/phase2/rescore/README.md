# Phase 2 re-scored: the answer must survive

The first scoring counted a needed turn as reached when any note of it was admitted. Compression (keeping a note's
sentences that share words with the question) and chunking (a long turn split in 120-token notes) can admit a note
of the turn without the sentence that holds the answer. Each LongMemEval question now names its evidence (the gold
answer when the turn says it, else the turn's sentence most like the gold answer; when neither can be told, a note
of the turn must be shown whole), and passes only if that evidence is in the rendered context.

LongMemEval only (260 questions; the CAMR probes and needles are notes of one or two sentences, which compression leaves whole). Pass rates per ability, and over the 230 answerable questions of A1-A4 and A6:

| Run | A1 | A2 | A3 | A4 | A6 | A7 | Answerable pass (95% CI) | First rule | Mean context tokens | Pass per 100 tokens | Answer cut / in another chunk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 78% | 28% | 65% | 42% | 70% | 13% | 60% (53–66) | 64% | 319 | 0.187 | 0 / 8 |
| step3-aggregate | 76% | 28% | 62% | 42% | 73% | 10% | 59% (53–65) | 67% | 391 | 0.151 | 24 / 8 |
| budget-512 | 80% | 35% | 68% | 45% | 77% | 10% | 63% (57–69) | 71% | 504 | 0.126 | 23 / 6 |
| budget-768 | 84% | 50% | 78% | 62% | 83% | 10% | 73% (67–78) | 80% | 724 | 0.101 | 21 / 7 |
| compress-384 | 68% | 12% | 48% | 20% | 80% | 10% | 48% (41–54) | 76% | 404 | 0.118 | 105 / 0 |
| compress-512 | 69% | 12% | 48% | 20% | 83% | 10% | 49% (42–55) | 81% | 507 | 0.096 | 115 / 0 |
| final | 68% | 12% | 48% | 20% | 80% | 17% | 48% (41–54) | 76% | 404 | 0.118 | 105 / 0 |

By the kind of evidence the needed facts have (answerable A1-A4, A6). *Gold answer in the turn* is the most objective: the reader needs that exact string.

| Run | Gold answer in the turn (n=69) | Sentence most like the answer (n=57) | Nothing to check: a note shown whole (n=78) |
|---|---|---|---|
| baseline | 80% | 61% | 56% |
| step3-aggregate | 80% | 63% | 54% |
| budget-512 | 83% | 67% | 59% |
| budget-768 | 84% | 74% | 74% |
| compress-384 | 77% | 68% | 18% |
| compress-512 | 78% | 70% | 18% |
| final | 77% | 68% | 18% |

Runs: **baseline** baseline read path (every Phase 2 flag off); **step3-aggregate** dates, time filter, profile, aggregate; 384 tokens, whole notes; **budget-512** step 3 at 512 tokens, whole notes; **budget-768** step 3 at 768 tokens, whole notes; **compress-384** step 3 + compression, 384 tokens; **compress-512** step 3 + compression, 512 tokens; **final** CAMR Personal's Phase 2 configuration (compression 384 + slot gate).

Evidence used (answerable questions' needed facts): string 79, none 167, sentence 90.
