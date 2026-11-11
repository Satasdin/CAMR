# KV trial 2: sparse line numbers against citation accuracy

11 November 2026, following D-62. `trials/kv/citations.py`. A pack of BurrowCore code is the system message, shown in
four forms. The model is asked where each of 40 names is declared ("Reply with only the file and line"). Each name is
declared once, so the right line is known. Temperature 0. Qwen3 4B Instruct 2507 Q4_K_M ran on llama-server
(q8_0 cache); Gemma 4 12B ran on Ollama's 16k alias with thinking off, because Gemma 4 thinks by default and spent
the answer's 40 tokens on it (a first run, overwritten, came back empty).

| Model, pack | Form | Tokens | Exact | Within 1 | Within 3 |
|---|---|---|---|---|---|
| Qwen3 4B, 6 files | every line | 10,450 | 29 | 32 | 33 |
| | every 5th | 8,720 | 9 | 15 | 32 |
| | every 10th | 8,502 | 0 | 5 | 22 |
| | none | 8,282 | 0 | 2 | 4 |
| Qwen3 4B, 9 files | every line | 20,989 | 27 | 33 | 34 |
| | every 5th | 17,320 | 8 | 17 | 27 |
| | every 10th | 16,856 | 7 | 12 | 22 |
| | none | 16,392 | 1 | 2 | 6 |
| Gemma 4 12B, 6 files | every line | 11,600 | 38 | 39 | 39 |
| | every 5th | 9,816 | 18 | 26 | 38 |
| | every 10th | 9,591 | 8 | 22 | 37 |
| | none | 9,365 | 2 | 7 | 14 |

Neither model counts lines reliably from a sparse mark, and the 4B can't count at all past a few lines. Every line
stays numbered. Most of the 4B's misses with full numbering name a line where the name is used, not declared.
The 4B's answers were re-scored once, after the parser was taught to read a bare "15:" answer; that changed only
full numbering (28 to 29, 26 to 27). Read times were not measured: the GPU was shared with Evaluation 3.
