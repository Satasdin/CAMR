# Model-size sweep: same engine, different small models

| model | benchmark | task_type | metric | floor | with_memory | ceiling_20b | gain | gap_closed | beats_ceiling | ceiling_kimi | gap_closed_vs_kimi | decode_tok_s_floor | decode_tok_s_memory | decode_change_pct | prompt_tokens_floor | prompt_tokens_memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma3:12b | gsm8k | reasoning | accuracy | 0.917 | 0.900 | - | -0.017 | - | - | - | - | 2.687 | 2.396 | -10.817 | 113.167 | 671.400 |
| gemma3:12b | hotpotqa | multi_hop | em | 0.300 | 0.630 | - | 0.330 | - | - | - | - | 3.660 | 3.577 | -2.248 | 47.433 | 499.407 |
| gemma3:12b | popqa | single_hop | contains | 0.333 | 0.793 | - | 0.460 | - | - | - | - | 3.871 | 3.705 | -4.285 | 37.300 | 360.759 |
| granite3.3:8b | gsm8k | reasoning | accuracy | 0.583 | 0.727 | - | 0.144 | - | - | - | - | 3.897 | 3.528 | -9.468 | 156.083 | 755.727 |
| granite3.3:8b | hotpotqa | multi_hop | em | 0.333 | 0.500 | - | 0.167 | - | - | - | - | 5.046 | 4.312 | -14.543 | 86.100 | 661.667 |
| granite3.3:8b | popqa | single_hop | contains | 0.167 | 0.800 | - | 0.633 | - | - | - | - | 4.989 | 4.644 | -6.912 | 72.700 | 482.667 |
| mistral:7b | gsm8k | reasoning | accuracy | 0.333 | 0.500 | - | 0.167 | - | - | - | - | 4.401 | 4.207 | -4.420 | 116.000 | 700.667 |
| mistral:7b | hotpotqa | multi_hop | em | 0.133 | 0.433 | - | 0.300 | - | - | - | - | 5.230 | 5.297 | 1.289 | 45.600 | 570.633 |
| mistral:7b | popqa | single_hop | contains | 0.300 | 0.767 | - | 0.467 | - | - | - | - | 5.376 | 5.126 | -4.650 | 34.300 | 409.700 |
| olmo2:7b | gsm8k | reasoning | accuracy | 0.636 | 0.833 | - | 0.197 | - | - | - | - | 4.381 | 3.773 | -13.879 | 135.818 | 611.000 |
| olmo2:7b | hotpotqa | multi_hop | em | 0.367 | 0.586 | - | 0.220 | - | - | - | - | 6.427 | 5.453 | -15.143 | 71.667 | 521.379 |
| olmo2:7b | popqa | single_hop | contains | 0.233 | 0.767 | - | 0.533 | - | - | - | - | 5.818 | 5.279 | -9.256 | 61.600 | 384.433 |
