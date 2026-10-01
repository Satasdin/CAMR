# Model-size sweep: same engine, different small models

| model | benchmark | task_type | metric | floor | with_memory | ceiling_20b | gain | gap_closed | beats_ceiling | ceiling_kimi | gap_closed_vs_kimi | decode_tok_s_floor | decode_tok_s_memory | decode_change_pct | prompt_tokens_floor | prompt_tokens_memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| falcon3:3b | gsm8k | reasoning | accuracy | 0.333 | 0.667 | - | 0.333 | - | - | - | - | 11.270 | 10.411 | -7.621 | 117.000 | 704.417 |
| falcon3:3b | hotpotqa | multi_hop | em | 0.133 | 0.500 | - | 0.367 | - | - | - | - | 14.798 | 14.227 | -3.857 | 48.567 | 529.333 |
| falcon3:3b | popqa | single_hop | contains | 0.100 | 0.700 | - | 0.600 | - | - | - | - | 14.205 | 14.549 | 2.424 | 38.367 | 382.033 |
| gemma3:1b | gsm8k | reasoning | accuracy | 0.333 | 0.167 | - | -0.167 | - | - | - | - | 18.973 | 17.475 | -7.898 | 113.167 | 669.667 |
| gemma3:1b | hotpotqa | multi_hop | em | 0.167 | 0.400 | - | 0.233 | - | - | - | - | 24.795 | 22.341 | -9.897 | 47.433 | 511.767 |
| gemma3:1b | popqa | single_hop | contains | 0.067 | 0.667 | - | 0.600 | - | - | - | - | 24.878 | 23.891 | -3.967 | 37.300 | 369.967 |
| granite3.3:2b | gsm8k | reasoning | accuracy | 0.583 | 0.583 | - | 0.000 | - | - | - | - | 10.916 | 9.348 | -14.365 | 156.083 | 762.333 |
| granite3.3:2b | hotpotqa | multi_hop | em | 0.267 | 0.433 | - | 0.167 | - | - | - | - | 15.226 | 11.798 | -22.513 | 86.100 | 661.667 |
| granite3.3:2b | popqa | single_hop | contains | 0.167 | 0.767 | - | 0.600 | - | - | - | - | 14.219 | 12.211 | -14.118 | 72.700 | 482.667 |
| phi4-mini:3.8b | gsm8k | reasoning | accuracy | 0.833 | 0.917 | - | 0.083 | - | - | - | - | 8.480 | 7.268 | -14.292 | 100.583 | 572.667 |
| phi4-mini:3.8b | hotpotqa | multi_hop | em | 0.100 | 0.400 | - | 0.300 | - | - | - | - | 11.452 | 10.180 | -11.109 | 38.267 | 482.667 |
| phi4-mini:3.8b | popqa | single_hop | contains | 0.133 | 0.800 | - | 0.667 | - | - | - | - | 12.559 | 10.672 | -15.026 | 28.467 | 346.533 |
| smollm2:1.7b | gsm8k | reasoning | accuracy | 0.333 | 0.417 | - | 0.083 | - | - | - | - | 11.501 | 9.531 | -17.130 | 134.333 | 699.333 |
| smollm2:1.7b | hotpotqa | multi_hop | em | 0.133 | 0.367 | - | 0.233 | - | - | - | - | 14.918 | 12.618 | -15.420 | 68.367 | 559.967 |
| smollm2:1.7b | popqa | single_hop | contains | 0.200 | 0.733 | - | 0.533 | - | - | - | - | 15.205 | 13.765 | -9.476 | 57.700 | 408.767 |
