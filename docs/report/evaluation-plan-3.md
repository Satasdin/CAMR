# Evaluation plan 3: memory any model can pick up

Written on 11 November 2026, before any of the parts it tests existed and before any scored run. Evaluation 2 (`evaluation-plan-2.md`) stays frozen as it is; nothing here changes its binary or its results.

## What is added

1. **The Ledger.** What an AI understood, decided, was corrected on, and where it stopped, kept as commits in the vault: `burrow commit`, `log`, `resume`, `blame`, `diff`, `revert`, and the same as MCP tools (`burrow_commit` and the rest). Every commit cites the files it rests on with their content hashes, and goes stale when one of them changes.
2. **Hooks.** Claude Code's session start, compaction and stop, and git's post-commit, write and read the Ledger without the model choosing a tool.
3. **The trust line.** Every lookup result starts with how much the vault holds for it: strong, thin, or nothing, and whether a correction exists.
4. **One door.** A model sees four tools by default (`burrow_find`, `burrow_read`, `burrow_resume`, `burrow_commit`) instead of twelve. The old names keep working.

## Frozen binary

Before the first scored run the engine is built once and frozen as `trials/ledger/work/bin/burrow-evaluation-3`. Its SHA-256 goes in every results folder's `meta.json`. No engine source changes after the first scored run; faults found later are reported, not fixed.

## Thresholds

The trust line uses the closeness the engine already measures (D-52): "nothing" below 0.40, "thin" from 0.40 to 0.52, "strong" above. These are the Evaluation 2 thresholds and are not tuned here.

## Claims, tests and baselines

| Part | Claim | Test | Compared with |
| --- | --- | --- | --- |
| Ledger resume | A model that lost its memory carries on as well as one given the whole transcript, while reading far fewer tokens | The connect trial's handoff test (T3): model A holds a conversation, model B is asked about it | Nothing; the pasted transcript; today's handoff (`Carry.handoff`) |
| A bigger model's notes | Qwen3 4B answers more questions right when it can read checked commits Claude left while answering *other* questions on the same vault | Evaluation 2's knowledge questions, split in half by a fixed seed: Claude answers half A and commits what it learned; the 4B answers half B with and without those commits | 4B alone; 4B with the engine; Claude alone as the ceiling |
| Trust line | The 4B says the vault does not hold the answer when it does not, without refusing answerable questions | 30 questions the vault cannot answer, written by a separate agent and checked against the vault's text, mixed with 30 answerable ones from Evaluation 2 | The same model without the trust line |
| One door | The 4B calls a fitting tool more often with four tools than with twelve | The connect trial's tool-choice test (T2), where the catalogue raised Qwen3 4B from 5/16 to 16/16 | Twelve tools with the catalogue |

The split for the notes test is made before any notes are written, so no note can contain an answer from half B. Every note is a commit whose cited lines are checked; a note that cites lines it was not shown is dropped.

## Models

Qwen3 4B (small, local), Gemma 4 12B (main, local), Claude (cloud). Temperature 0 everywhere.

## Measures

- Accuracy, by the Evaluation 2 rule: an answer is right when it contains every required string of its key.
- Tokens the receiving model reads to carry on (handoff test).
- For the trust line: the share of unanswerable questions answered "not in the vault", and the share of answerable ones wrongly refused.
- Tool-choice accuracy: a lookup tool called when one is needed, and the right one.
- Exact two-sided sign test on paired answers for each comparison.

## Predictions, stated before the runs

- Ledger resume matches the pasted transcript on accuracy and reads under a quarter of its tokens.
- Notes from the bigger model raise the 4B on multi-fact questions more than on single-fact ones.
- The trust line raises honest "not in the vault" answers well above today's level and costs at most a few answerable questions.
- One door matches or beats twelve tools on the 4B, and the difference shrinks on Gemma 4 12B.

## Changes after the smoke run, before any scored run (11 November 2026)

A smoke run (`--quick`, four questions per test, results discarded) checked that every test runs end to end. It found two faults in the engine and one in the harness. All were fixed and the binary was frozen again before the first scored run. No threshold or wording was tuned on what the smoke run's answers said.

1. `burrow resume` cut "where the last session stopped" to 700 characters, so a handoff kept only its first answered turn. It now gets up to 1,500 characters, and each turn's answer is kept to 240 characters.
2. Qwen3 4B called `burrow_resume` with a branch it made up ("last_conversation") and was told nothing had been kept. An unknown branch now falls back to the current one, and the reply says so.
3. Harness: a program that reconnects within 30 minutes carries on its earlier session (D-45 era behaviour, by design), so the five test conversations merged into one session. Each test conversation now names itself apart. The harness also hands a refused tool call back to the model as an error instead of stopping.
