> **Correction (2026-10-22, re-scored).** The tables below used a first scoring rule that counted a needed fact as
> reached when any note of its turn was admitted. With `compress = sentences` that is wrong: compression keeps a
> note's sentences that share words with the question, and the sentence holding the answer often shares none ("I
> upgraded to 500 Mbps" vs "What speed is my new internet plan?"). The reader bench found it (Kimi K3 recall
> fell). Re-scored so that the answer must survive in the rendered context (`rescore/README.md`), compression
> *loses*: answerable pass 48% at 384 tokens against 59% for whole notes, and 77% against 80% on the questions
> whose gold answer is in the turn verbatim. The step-4 gains (A2 52%, A3 81%, A4 67%) are not real. Whole notes
> win: 384 tokens is the most efficient (0.151 passes per 100 tokens), 512 adds 4 points (63%), 768 adds 14 (73%).
> Compression was chosen under a rule that did not check whether the answer survived, and was reversed: CAMR
> Personal now uses whole notes at 512 tokens, with tightened profile notes (`phase2b` in the table below).
