# Reader bench: phase2

Each reader answers every question alone and with what CAMR Personal's memory admitted (the app's own chat prompt). Right/wrong by the judge with LongMemEval's per-type rules; help = wrong alone and right with memory, harm = right alone and wrong with memory.

## Overall

| Reader | right alone | right with memory | help | harm | declined with memory | s per answer (memory) | prompt tokens (memory) |
|---|---|---|---|---|---|---|---|
| kimi-k3 | 20% | 76% | 165 | 4 | 24% | 13.26 | 706 |
| qwen2.5:0.5b | 11% | 33% | 75 | 12 | 24% | 0.96 | 706 |
| qwen2.5:1.5b | 17% | 50% | 108 | 14 | 23% | 2.10 | 706 |
| qwen2.5:3b | 16% | 60% | 132 | 6 | 24% | 3.61 | 706 |

## Right with memory, by ability (right alone in brackets)

| Ability | kimi-k3 | qwen2.5:0.5b | qwen2.5:1.5b | qwen2.5:3b |
|---|---|---|---|---|
| A1 recall a fact | 81% (11%) n=80 | 46% (1%) n=80 | 68% (2%) n=80 | 75% (4%) n=80 |
| A10  | 100% (100%) n=12 | 83% (83%) n=12 | 92% (92%) n=12 | 100% (100%) n=12 |
| A2 join facts | 45% (0%) n=40 | 10% (0%) n=40 | 15% (2%) n=40 | 25% (0%) n=40 |
| A3 fact changed | 81% (0%) n=43 | 30% (0%) n=43 | 49% (2%) n=43 | 67% (0%) n=43 |
| A4 time | 74% (2%) n=42 | 15% (19%) n=42 | 48% (7%) n=42 | 45% (0%) n=42 |
| A5 counting | 67% (0%) n=3 | 0% (0%) n=3 | 0% (0%) n=3 | 0% (0%) n=3 |
| A6 preference | 78% (3%) n=33 | 30% (6%) n=33 | 30% (6%) n=33 | 48% (3%) n=33 |
| A7 say I don't know | 88% (100%) n=34 | 41% (29%) n=34 | 65% (88%) n=34 | 79% (91%) n=34 |

Cloud tokens this report covers: Kimi as reader 297,639 in / 156,657 out; judge 602,619 in / 295,836 out; about $9.49 at list price (cached calls are counted when first made). Judge disagreements with the model-free contains-gold check: 251 of 2022.
