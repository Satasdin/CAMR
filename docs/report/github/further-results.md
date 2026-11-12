
The tables below support Section 5.5, and the two trials at the end of this page lie outside the specific objectives. Table R1 gives the small model, Table R2 the main model by subject, and Table R3 the paired tests. Table R4 and Table R5 give what the engine decided, Table R6 where the wrong answers came from, and Table R7 one question of each kind. Every answer is saved in the repository under trials/results/gap-1, and the full record of the 212 automated tests is in unit-tests-evaluation-2.log in the same folder.

!include generated2/accuracy-qwen3.5-4b.md

!include generated2/subjects.md

!include generated2/sign.md | Table R3 | 1.15,2.4,0.9,0.6,0.7,0.6

!include generated2/decisions.md

!include generated2/wrong.md | Table R6 | 1.15,1.8,0.8,1.3,1.3

!include generated2/examples.md | Table R7 | 1.1,2.9,2.3

Before the engine's five steps were built, retrieval alone was tested at tag evaluation-1. On 101 real bug fixes from four public repositories, following links reached a changed file on 72 and plain search on 59 (p = 0.002). On three held-back synthetic projects worked by simulated developer agents, memory did not measurably help the small model write working code. The simulated agents were programs, and no person took part. Those results are saved under trials/results and led to the engine described in this report.

### A Coding Trial Against the Cloud Model

A small trial asked whether the on-device model can build something beside the cloud model. Three briefs for a single-file website were given to Gemma 4 12B and to Claude: a matatu fare splitter, a clinic queue board that survives a reload, and a landing page with a phone menu and a pricing toggle. Each page was scored in a real browser with the same fixed checks, 42 in all. Figure R1 shows the pages.

!fig figures/v2/web-compare.png | Figure R1: The same three briefs built by Gemma 4 12B alone, by Gemma with a skill and a note of known failures, and by Claude alone | 6.2

Claude passed all 42 checks in every set-up. Gemma alone passed 41. With the brief the engine prepared, which carried a web-building skill, Gemma passed 39, because one page had a script error. With the skill and a note of known failures handed over directly, it passed 41, and that run had no such error. The engine had left the note out, because it judged each brief to be a task to work out. The trial is three briefs run once, so it is a demonstration and not a measurement.

### A Further Evaluation of Session Memory

A third evaluation, planned in advance like the second and run on a frozen binary, tested features added after the objectives were met. It used Qwen3 4B, a different model from the Qwen3.5 4B of Chapter 5, and its own 40 knowledge questions, half of the Evaluation 2 set split by a fixed seed, so its counts are not comparable with Table 5.5. None of the four features improved on its baseline. Table R8 shows that a pasted transcript carried a conversation further than the Ledger's handoff. Table R9 shows that notes Claude left on the other half of the questions added one answer to Burrow's 28 of 40. Table R10 shows that the line telling the model how much the vault holds did not change how often it declined, and Table R11 that four tools did no better than twelve. The plan, the frozen binary, every answer and the analysis are in the repository under trials/ledger and docs/report/evaluation-plan-3.md.

!include generated3/e1-resume.md | Table R8

!include generated3/e2-notes.md | Table R9

!include generated3/e3-trust.md | Table R10

!include generated3/e4-door.md | Table R11

