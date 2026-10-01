# Model-size sweep: same engine, different small models

| model | benchmark | task_type | metric | floor | with_memory | ceiling_20b | gain | gap_closed | beats_ceiling | ceiling_kimi | gap_closed_vs_kimi | decode_tok_s_floor | decode_tok_s_memory | decode_change_pct | prompt_tokens_floor | prompt_tokens_memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma3:4b | gsm8k | reasoning | accuracy | 0.750 | 0.500 | - | -0.250 | - | - | - | - | 6.980 | 6.706 | -3.936 | 113.167 | 669.667 |
| gemma3:4b | hotpotqa | multi_hop | em | 0.200 | 0.533 | - | 0.333 | - | - | - | - | 9.278 | 9.250 | -0.293 | 47.433 | 511.767 |
| gemma3:4b | popqa | single_hop | contains | 0.200 | 0.733 | - | 0.533 | - | - | - | - | 9.897 | 9.069 | -8.369 | 37.300 | 369.967 |
| llama3.2:1b | gsm8k | reasoning | accuracy | 0.583 | 0.333 | - | -0.250 | - | - | - | - | 27.561 | 25.541 | -7.331 | 124.500 | 599.000 |
| llama3.2:1b | hotpotqa | multi_hop | em | 0.167 | 0.400 | - | 0.233 | - | - | - | - | 35.536 | 31.622 | -11.014 | 60.600 | 511.233 |
| llama3.2:1b | popqa | single_hop | contains | 0.100 | 0.633 | - | 0.533 | - | - | - | - | 36.231 | 33.662 | -7.090 | 50.567 | 372.567 |
| llama3.2:3b | gsm8k | reasoning | accuracy | 0.750 | 0.750 | - | 0.000 | - | - | - | - | 8.488 | 7.784 | -8.299 | 124.500 | 599.000 |
| llama3.2:3b | hotpotqa | multi_hop | em | 0.167 | 0.567 | - | 0.400 | - | - | - | - | 11.048 | 10.425 | -5.637 | 60.600 | 511.233 |
| llama3.2:3b | popqa | single_hop | contains | 0.233 | 0.733 | - | 0.500 | - | - | - | - | 11.831 | 10.443 | -11.729 | 50.567 | 372.567 |
| qwen2.5:0.5b | gsm8k | reasoning | accuracy | 0.250 | 0.167 | - | -0.083 | - | - | - | - | 40.255 | 37.357 | -7.198 | 131.583 | 678.917 |
| qwen2.5:0.5b | hotpotqa | multi_hop | em | 0.100 | 0.300 | - | 0.200 | - | - | - | - | 48.021 | 46.074 | -4.053 | 65.067 | 538.467 |
| qwen2.5:0.5b | popqa | single_hop | contains | 0.067 | 0.667 | - | 0.600 | - | - | - | - | 50.285 | 48.853 | -2.849 | 54.600 | 393.267 |
| qwen2.5:1.5b | gsm8k | reasoning | accuracy | 0.583 | 0.417 | - | -0.167 | - | - | - | - | 16.402 | 15.562 | -5.125 | 131.583 | 678.917 |
| qwen2.5:1.5b | hotpotqa | multi_hop | em | 0.167 | 0.500 | - | 0.333 | - | - | - | - | 21.494 | 21.843 | 1.624 | 65.067 | 538.467 |
| qwen2.5:1.5b | popqa | single_hop | contains | 0.100 | 0.800 | - | 0.700 | - | - | - | - | 21.435 | 19.897 | -7.178 | 54.600 | 393.267 |
| qwen2.5:3b | gsm8k | reasoning | accuracy | 0.250 | 0.333 | - | 0.083 | - | - | - | - | 8.782 | 8.471 | -3.540 | 131.583 | 678.917 |
| qwen2.5:3b | hotpotqa | multi_hop | em | 0.333 | 0.433 | - | 0.100 | - | - | - | - | 12.061 | 11.599 | -3.829 | 65.067 | 538.467 |
| qwen2.5:3b | popqa | single_hop | contains | 0.067 | 0.800 | - | 0.733 | - | - | - | - | 13.263 | 11.017 | -16.933 | 54.600 | 393.267 |
