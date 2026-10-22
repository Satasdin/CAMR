# Reader bench: baseline

Each reader answers every question alone and with what CAMR Personal's memory admitted (the app's own chat prompt). Right/wrong by the judge with LongMemEval's per-type rules; help = wrong alone and right with memory, harm = right alone and wrong with memory.

## Overall

| Reader | right alone | right with memory | help | harm | declined with memory | s per answer (memory) | prompt tokens (memory) |
|---|---|---|---|---|---|---|---|
| qwen2.5:0.5b | 11% | 37% | 87 | 14 | 18% | 3.41 | 561 |
| qwen2.5:1.5b | 16% | 48% | 102 | 11 | 21% | 2.29 | 561 |
| qwen2.5:3b | 17% | 55% | 116 | 5 | 25% | 3.15 | 561 |
| kimi-k3 | 21% | 73% | 154 | 4 | 29% | 9.41 | 589 |

## Right with memory, by ability (right alone in brackets)

| Ability | qwen2.5:0.5b | qwen2.5:1.5b | qwen2.5:3b | kimi-k3 |
|---|---|---|---|---|
| A1 recall a fact | 60% (2%) n=80 | 71% (4%) n=80 | 76% (2%) n=80 | 88% (15%) n=80 |
| A10  | 83% (83%) n=12 | 100% (100%) n=12 | 100% (100%) n=12 | 100% (100%) n=12 |
| A2 join facts | 12% (0%) n=40 | 22% (0%) n=40 | 28% (0%) n=40 | 40% (0%) n=40 |
| A3 fact changed | 40% (0%) n=43 | 51% (0%) n=43 | 58% (0%) n=43 | 77% (0%) n=43 |
| A4 time | 24% (14%) n=42 | 21% (5%) n=42 | 24% (0%) n=42 | 50% (0%) n=42 |
| A5 counting | 0% (0%) n=3 | 0% (0%) n=3 | 0% (0%) n=3 | 33% (0%) n=3 |
| A6 preference | 12% (3%) n=33 | 27% (3%) n=33 | 33% (3%) n=33 | 73% (3%) n=33 |
| A7 say I don't know | 35% (41%) n=34 | 56% (82%) n=34 | 85% (97%) n=34 | 94% (100%) n=34 |

Cloud tokens this report covers: Kimi as reader 254,145 in / 160,172 out; judge 604,930 in / 290,965 out; about $9.34 at list price (cached calls are counted when first made). Judge disagreements with the model-free contains-gold check: 224 of 2024.
