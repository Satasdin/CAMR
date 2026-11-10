!tab Table 5.13: Cost of an answer on knowledge questions: tokens read, seconds, and whether the evidence was retrieved
!widths 0.9,1.6,0.8,0.8,0.9,1.2
| Model | Set-up | Median tokens read | Median seconds | Median seconds before the model | Every evidence file retrieved |
| Gemma 4 12B | Model alone | 82 | 1.6 | - | - |
| Gemma 4 12B | Plain retrieval | 3814 | 8.3 | 0.43 | 102 of 120 (85%) |
| Gemma 4 12B | Vector database (Chroma) | 3440 | 5.5 | 0.04 | 95 of 120 (79%) |
| Gemma 4 12B | Burrow engine | 6068 | 9.2 | 0.06 | 111 of 120 (92%) |
| Qwen3.5 4B | Model alone | 82 | 1.6 | - | - |
| Claude | Cloud model alone | 97 | 2.8 | - | - |
| Claude | Cloud model with Burrow | 10496 | 6.7 | - | 116 of 120 (97%) |
