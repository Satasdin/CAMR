# Evaluation plan 2: the engine and the capability gap

Written on 10 November 2026, before any scored run of this evaluation. It adds to `evaluation-plan.md`, whose results (tag `evaluation-1`) stay in the report as the state before the engine.

## What changed since evaluation-1

1. Search keeps its vectors as one memory-mapped block and reads the word index once per question.
2. The engine decides whether a question needs the vault, and whether to search or follow links.
3. The engine measures the hosted model once and sets how much it is shown.
4. Every file and line an answer cites is checked against what the model was shown. A wrong citation gets one retry.
5. A conversation's decisions can be written down as notes, each backed by the person's own words, with consent.
6. The vault holds skills: short methods for kinds of task. One is handed to the model with the question.
7. The rule on reasons is given only when a question asks why. Before, a small model opened factual answers with "The reason is not recorded."

## Frozen binary

The engine is frozen as the binary `trials/gap/work/bin/burrow-evaluation-2`, whose SHA-256 is written to each results folder's `meta.json`, with the source difference from `evaluation-1` saved beside it. No engine source is changed after the first scored run. Faults found later are reported, not fixed.

## Thresholds and how they were set

All were set on questions written by the developer for that purpose, never on the scored tasks. Nobody tuning the engine read the scored tasks.

- Vault closeness below 0.40: the vault is left out. Set from 11 development questions.
- Closeness 0.40 to 0.52 with a clearly matched skill that needs no vault: the vault is left out.
- A skill is matched at closeness 0.55 or more and 0.10 clear of the next skill. Set from the 26 labelled questions in `trials/gap/dev/skill-calibration.py`: 9 matched: 8 to the labelled method, 1 two-fact question to the documents method, and none on a question that wanted no skill.
- Otherwise the method follows the material: one for documents, one for code.

## Tasks (written by separate agents; checked by script against the vault's text)

- Knowledge, law: 25 single-fact and 15 multi-fact questions on Kenya's Data Protection Act and its 2021 regulations.
- Knowledge, software: 25 single-fact and 15 multi-fact questions on documentation published in 2026.
- Knowledge, private project: 25 single-fact and 15 multi-fact questions on Burrow's own source and decisions at `evaluation-1`.
- Reasoning: 50 questions from the GSM8K test split, chosen with a fixed seed.

An answer is right when it contains every required string of its key (any one of the listed forms). A reasoning answer is right when its last number equals the key.

## Set-ups

1. Local model alone.
2. Local model with plain retrieval (the evaluation-1 search, 12,000 characters): the database set-up.
3. Local model with the engine.
4. Local model with a standard vector database pipeline (Chroma, same embedding model, 12,000 characters): the baseline.
5. Cloud model alone.
6. Cloud model with the engine's brief.

Local models: Gemma 4 12B (main) and Qwen3.5 4B (small). Cloud model: Claude. Temperature 0 everywhere.

## Measures and tests

- Accuracy per set-up, subject and task type.
- Fraction of the gap closed: (local with memory − local alone) / (cloud alone − local alone), per task type. Not defined where the cloud is not ahead.
- Tokens read and seconds per answer, with the time spent before the model is called reported separately.
- Exact two-sided sign test on paired answers: engine against alone, against plain retrieval, and against Chroma.
- Ablation on the main model: the engine without skills, and without the check.

## Predictions, stated before the runs

- Knowledge tasks: the engine closes most of the gap. On the private project the cloud model alone cannot know the answers, so the gap there is reported against the cloud model with the same memory.
- Reasoning tasks: memory closes little or none of the gap, as the proposal predicted. Whether a skill helps is an open question.
- The engine reads more tokens than plain retrieval on the main model, because it fits the budget to the model.

## Limits known in advance

- The questions were written by a language model from the documents, not by people.
- The answer keys accept an answer that contains the right string for the wrong reason.
- One machine, one run per question at temperature 0.
- The 101 real bug fixes were the held-out set of evaluation-1. For evaluation-2 they are a regression check only, since the new search was developed after their results were seen.
