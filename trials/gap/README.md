# The gap trial

The same questions are put to several set-ups. Every answer is marked right or wrong by a fixed rule.
Then one number is worked out:

    gap closed = (local with memory − local alone) / (cloud alone − local alone)

It says how much of the distance between a small model on this Mac and a large cloud model is
covered by giving the small model a memory. It is reported per subject and per task type, with the
tokens and seconds each answer cost.

## The set-ups

| name | what it is |
|---|---|
| `local_alone` | the local model with no memory (`burrow ask --mode none`) |
| `local_database` | plain retrieval pasted into the prompt, the "database" set-up (`burrow ask --mode search`) |
| `local_engine` | the full Burrow engine (`burrow ask --mode engine`) |
| `local_engine_noskills` | the engine without its method files (`--mode engine --no-skills`), to see what they add |
| `local_engine_nocheck` | the engine without its answer check (`--mode engine --no-check`), to see what it adds |
| `chroma` | an ordinary vector-database pipeline as the outside baseline: every text file in the vault cut into pieces of about 1,200 characters (150 overlap), embedded with `qwen3-embedding:0.6b`, kept in Chroma, nearest pieces by cosine up to 12,000 characters, then the same local model through Ollama. Dot folders, any `Skills` folder (the engine's method files) and the store are not indexed |
| `cloud_alone` | the cloud model with no memory |
| `cloud_engine` | the cloud model given the prompt Burrow prepares (`burrow brief`) |

## Set up once

    cd trials/gap
    /usr/bin/python3 -m venv .venv
    .venv/bin/pip install chromadb langchain-core anthropic

Ollama must be running with the local model and `qwen3-embedding:0.6b` pulled. The cloud set-ups read
the key from `~/.config/camr/anthropic.env` (a line `ANTHROPIC_API_KEY=...`). The key is only held in
memory; it is never printed or written anywhere.

## 1. Build the reasoning questions

    .venv/bin/python reasoning.py

Downloads the official GSM8K test file to `work/gsm8k/test.jsonl`, picks 50 with a fixed seed and
writes `tasks/reasoning.jsonl`. Where the file came from and its sha256 are in
`tasks/reasoning.source.json`.

## 2. Run

Local set-ups, one folder per local model:

    .venv/bin/python run.py --tasks tasks/knowledge.jsonl tasks/project.jsonl tasks/reasoning.jsonl \
        --setups local_alone local_database chroma local_engine local_engine_noskills local_engine_nocheck \
        --model gemma4:12b --vault vault --out results/gemma4-12b

Cloud set-ups, in their own folder (they do not depend on the local model):

    .venv/bin/python run.py --tasks tasks/knowledge.jsonl tasks/project.jsonl tasks/reasoning.jsonl \
        --setups cloud_alone cloud_engine --cloud-model claude-sonnet-5-5 \
        --vault vault --out results/cloud-sonnet

Things to know:

- **It can be stopped and started.** Each answer is saved the moment it arrives. Run the same command
  again and questions already answered are skipped.
- **Nothing is overwritten.** If the out folder already holds results for a set-up made with a
  different model, a different burrow binary (by sha256), a different vault or a different cloud model,
  the run refuses to start. Use a new `--out` folder.
- **Errors are kept.** A call that fails or passes 300 seconds is recorded with an `"error"` and counted
  wrong. `--retry-errors` asks those questions again; the new line is added and the scorer uses the last
  line for each question. After 5 errors in a row a set-up is left (the usual cause is Ollama not
  running, or a binary without that mode).
- **Temperature.** Local calls use temperature 0. `claude-sonnet-5-5` answers "`temperature` is
  deprecated for this model", so the setting is left out for it; `meta.json` says so
  (`cloud_temperature_sent`).
- **Cloud spend is capped.** `--max-cloud-tokens` (default 3,000,000 input tokens, counted over the out
  folder) stops cloud calls before the limit and exits cleanly. The running total is in
  `cloud_usage.json`.
- `--limit 5` runs only the first five questions; `--ids a b` runs only those;
  `--only-types multi reasoning` and `--only-subjects law` run part of the tasks. The results file
  records every question it ran, and the scorer compares set-ups only on questions both answered.
- `--burrow PATH` picks the binary; `--store DIR` is where Burrow keeps its index (default
  `work/store`); `--chroma-dir DIR` is where Chroma keeps its pieces (default `work/chroma`).
- Burrow's index is refreshed at the start of each run (`--no-index` skips this).

What is written in the out folder:

- `<setup>.jsonl`: one line per question: `id`, `subject`, `type`, `answer`, `correct`, `seconds`,
  `prompt_tokens`, `answer_tokens`, `tokens`, `retrieve_s`, `excerpt_paths`, `excerpts`, `evidence`,
  `extra` (anything else Burrow returned: `route`, `skills`, `citations`, `retried`…), and `identity`
  (the model and binary the line was made with).
- `meta.json`: local model, cloud model, burrow path and sha256, date, Ollama version, sha256 of each
  task file, and a record of every time the command was run.

## 3. Score

    .venv/bin/python score.py results/gemma4-12b results/cloud-sonnet

Prints the summary and writes `summary.json` and `summary.md` into the first folder (or `--out`). It
gives:

- accuracy for each set-up × subject × type, with counts, median seconds and median prompt tokens;
- the gap closed for `local_database`, `chroma`, `local_engine` and the two ablations, per subject and per type. Where
  the cloud model is not better than the local model alone it says "not defined";
- an exact two-sided sign test for `local_engine` against `local_alone`, `local_database`, `chroma` and each ablation;
- evidence recall: of the questions that name evidence files, the share where every one of those files
  was among the retrieved excerpts.

## How an answer is marked

- **Knowledge questions** (`single`, `multi`): right when, for every group in `must_include`, at least
  one of its strings is in the answer. Case and spacing are ignored and `12,000` equals `12000`.
- **Reasoning questions**: right when the last number in the answer equals `answer`. File references
  such as `notes.md:3`, which Burrow's answers end with, are not counted as numbers. Every set-up gets
  the same extra sentence after a reasoning question: "Show your working briefly, then give the final
  answer as a number on the last line." (`--no-reasoning-suffix` turns it off.)

The rules are in `scoring.py` and checked by:

    .venv/bin/python test_score.py

## The small test set

`fixture/vault` (six short notes) and `fixture/tasks.jsonl` (six questions) are for checking the
harness, not for results:

    .venv/bin/python run.py --tasks fixture/tasks.jsonl --setups local_alone local_database chroma \
        --model qwen3:4b-instruct-2507-q4_K_M --vault fixture/vault \
        --store fixture/store --chroma-dir fixture/chroma --out fixture/results/local
    .venv/bin/python score.py fixture/results/local fixture/results/cloud

## Burrow inside LangChain

`adapters/langchain_burrow.py` is a LangChain retriever (`BurrowRetriever`) that calls `burrow find`
and returns the chosen lines as documents. `adapters/demo_langchain.py` is a small chain around it:

    .venv/bin/python adapters/demo_langchain.py "How deep is the Tumaini borehole?" \
        --vault fixture/vault --store fixture/store

It prints the answer and the files it used.
