!tab Table 5.6: Cost of an answer on knowledge questions: tokens read, seconds, and whether the evidence was retrieved
!widths 0.9,1.6,0.8,0.8,0.9,1.2
| Model | Set-up | Median tokens read | Median seconds | Median seconds before the model | Every evidence file retrieved |
| Gemma 4 12B | Model alone | 82 | 1.6 | - | - |
| Gemma 4 12B | Plain retrieval | 3814 | 8.3 | 0.43 | 102 of 120 (85%) |
| Gemma 4 12B | Vector database (Chroma) | 3440 | 5.5 | 0.04 | 95 of 120 (79%) |
| Gemma 4 12B | Burrow engine | 6068 | 9.2 | 0.06 | 111 of 120 (92%) |
| Qwen3.5 4B | Model alone | 85 | 1.5 | - | - |
| Qwen3.5 4B | Plain retrieval | 3708 | 4.0 | 0.06 | 102 of 120 (85%) |
| Qwen3.5 4B | Vector database (Chroma) | 3410 | 3.7 | 0.02 | 95 of 120 (79%) |
| Qwen3.5 4B | Burrow engine | 4126 | 3.2 | 0.05 | 103 of 120 (86%) |
| Claude | Cloud model alone | 97 | 2.8 | - | - |
| Claude | Cloud model with Burrow | 10496 | 6.7 | - | 116 of 120 (97%) |
