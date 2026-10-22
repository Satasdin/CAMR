# Reader bench: phase2b

Each reader answers every question alone and with what CAMR Personal's memory admitted (the app's own chat prompt). Right/wrong by the judge with LongMemEval's per-type rules; help = wrong alone and right with memory, harm = right alone and wrong with memory.

## Overall

| Reader | right alone | right with memory | help | harm | declined with memory | s per answer (memory) | prompt tokens (memory) |
|---|---|---|---|---|---|---|---|
| kimi-k3 | 20% | 78% | 170 | 3 | 25% | 10.36 | 762 |
| qwen2.5:0.5b | 11% | 39% | 89 | 9 | 23% | 1.33 | 758 |
| qwen2.5:1.5b | 17% | 51% | 110 | 13 | 24% | 2.07 | 758 |
| qwen2.5:3b | 16% | 58% | 124 | 5 | 28% | 4.57 | 758 |

## Right with memory, by ability (right alone in brackets)

| Ability | kimi-k3 | qwen2.5:0.5b | qwen2.5:1.5b | qwen2.5:3b |
|---|---|---|---|---|
| A1 recall a fact | 91% (11%) n=80 | 60% (1%) n=80 | 72% (2%) n=80 | 79% (4%) n=80 |
| A10  | 100% (100%) n=12 | 83% (83%) n=12 | 92% (92%) n=12 | 100% (100%) n=12 |
| A2 join facts | 45% (0%) n=40 | 10% (0%) n=40 | 15% (2%) n=40 | 28% (0%) n=40 |
| A3 fact changed | 77% (0%) n=43 | 23% (0%) n=43 | 49% (2%) n=43 | 65% (0%) n=43 |
| A4 time | 69% (2%) n=42 | 26% (19%) n=42 | 40% (7%) n=42 | 26% (0%) n=42 |
| A5 counting | 67% (0%) n=3 | 0% (0%) n=3 | 0% (0%) n=3 | 0% (0%) n=3 |
| A6 preference | 79% (3%) n=33 | 36% (6%) n=33 | 30% (6%) n=33 | 39% (3%) n=33 |
| A7 say I don't know | 91% (100%) n=34 | 47% (29%) n=34 | 71% (88%) n=34 | 82% (91%) n=34 |

Cloud tokens this report covers: Kimi as reader 206,410 in / 72,199 out; judge 605,901 in / 297,837 out; about $7.99 at list price (cached calls are counted when first made). Judge disagreements with the model-free contains-gold check: 250 of 2024.
