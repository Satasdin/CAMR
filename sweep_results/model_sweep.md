# Model-size sweep: same engine, different small models

| model | benchmark | task_type | metric | floor | with_memory | ceiling_20b | gain | gap_closed | beats_ceiling | decode_tok_s_floor | decode_tok_s_memory | decode_change_pct | prompt_tokens_floor | prompt_tokens_memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma2:9b | gsm8k | reasoning | accuracy | 0.750 | 0.667 | - | -0.083 | - | - | 5.624 | 4.841 | -13.918 | 112.167 | 668.583 |
| gemma2:9b | hotpotqa | multi_hop | em | 0.333 | 0.500 | - | 0.167 | - | - | 6.647 | 5.925 | -10.863 | 46.400 | 508.733 |
| gemma2:9b | popqa | single_hop | contains | 0.333 | 0.767 | - | 0.433 | - | - | 6.696 | 6.466 | -3.446 | 36.267 | 366.767 |
| llama3.1:8b | gsm8k | reasoning | accuracy | 0.833 | 0.583 | - | -0.250 | - | - | 4.296 | 4.054 | -5.638 | 109.500 | 584.000 |
| llama3.1:8b | hotpotqa | multi_hop | em | 0.367 | 0.567 | - | 0.200 | - | - | 5.693 | 5.169 | -9.200 | 45.600 | 496.233 |
| llama3.1:8b | popqa | single_hop | contains | 0.200 | 0.733 | - | 0.533 | - | - | 5.685 | 5.367 | -5.600 | 35.567 | 357.567 |
| qwen2.5:14b | gsm8k | reasoning | accuracy | 0.667 | 0.917 | - | 0.250 | - | - | 2.380 | 2.249 | -5.492 | 131.583 | 678.917 |
| qwen2.5:14b | hotpotqa | multi_hop | em | 0.467 | 0.633 | - | 0.167 | - | - | 3.152 | 2.959 | -6.139 | 65.067 | 538.467 |
| qwen2.5:14b | popqa | single_hop | contains | 0.133 | 0.733 | - | 0.600 | - | - | 3.237 | 2.969 | -8.268 | 54.600 | 393.267 |
| qwen2.5:7b | gsm8k | reasoning | accuracy | 0.833 | 0.833 | - | 0.000 | - | - | 4.649 | 4.485 | -3.538 | 131.583 | 678.917 |
| qwen2.5:7b | hotpotqa | multi_hop | em | 0.367 | 0.600 | - | 0.233 | - | - | 6.373 | 6.088 | -4.478 | 65.067 | 538.467 |
| qwen2.5:7b | popqa | single_hop | contains | 0.233 | 0.700 | - | 0.467 | - | - | 6.141 | 5.990 | -2.457 | 54.600 | 393.267 |
