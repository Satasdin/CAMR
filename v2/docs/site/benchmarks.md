# Benchmarks

The benchmarks ask one thing: does a small model on a Mac, with this memory, close the gap to a cloud model on long
work, without getting slower or heavier as the history grows? Every answer is graded by a rule, and every answer
records what it cost (see [Metrics](metrics.md)).

## Who is measured

| Model | Runtime | Memory as |
| --- | --- | --- |
| Qwen3 1.7B, Qwen3 4B Instruct 2507, Qwen3 8B | MLX, 4-bit | tensors (rooms and core) and the vault |
| Qwen 27B (`mlx-community/Qwen3.8-27B-4bit`) | MLX, 4-bit | words: its linear-attention layers keep no keys and values to save |
| Qwen3 1.7B, 4B, 8B | Ollama, through the pairing | words |
| Claude Haiku 5.5, Sonnet 5.5, Opus 5.5 | the Anthropic API | none: the yardstick |

Claude is only a yardstick. It answers the same questions on its own, with no memory engine.

## The Long Haul

Our own hard test. One scripted project: a developer building the site and back office of "Mama Njeri's Kitchen",
in Nairobi, over 110 working days. It mixes chat, meetings, decisions, code, documents, logs, a maths course and
noise. It is fixed by its seed: the same seed always gives the same script.

The built test for seed 1 has 17,786 events and 2,010,094 tokens (counted with Qwen3-1.7B's tokenizer), from 22
September 2025 to 27 February 2026.

### What it plants and asks

Probes are planted early and asked late. Each has one answer a rule can check.

| Family | Probes | Planted | Asked | Graded |
| --- | --- | --- | --- | --- |
| `fact` | 400 | facts at random depths | far past every window | exact |
| `changed` | 80 facts, 160 questions | each changed 2 to 4 times, with dates | the value now, and the value on a past date | exact; an old value is stale |
| `two_hop` | 40 | two halves, weeks apart | a question that needs both | exact |
| `maths` | 40 problems, 120 questions | a hard problem, a scripted first answer with the tempting wrong method, then a step-by-step correction; some corrections state a rule invented for this project | the same problem; the same method with new numbers; the invented rule on a new case | exact number; the uncorrected method's number is stale |
| `page` | 3 | a design system in week 1; the main colour changes on day 61 | "Build the catering page" on day 110 | HTML and CSS checks; optionally loaded in a headless browser |
| `code` | 20 | five helper modules with exact names, units and quirks | new code that calls them | unit tests run on the answer, in a sandbox |
| `lookalike` | 30 | two Wanjirus, prices 1 shilling apart, near-identical repo names | aimed at one of each pair | exact |
| `never` | 60 | nothing | questions on things never told | a decline is right; a guess is a false memory |

One example of an invented rule: the fee is 1% rounded up to the next 5 shillings, at least 10, and a flat 25 for
exact multiples of 1,000. So 12,000 gives 25 and 7,321 gives 75.

### The cuts and the checkpoints

The script is cut at four sizes. At each cut, a checkpoint takes a stratified sample of the probes askable there:
10 from each family (seed 0), each resolved to its right answer at that point. Every contender gets exactly these
checkpoints, so their scores compare.

| Cut | Tokens told | Events told | Last day | Questions |
| --- | --- | --- | --- | --- |
| 64K | 63,860 | 551 | 7 | 34 |
| 256K | 255,952 | 2,343 | 16 | 40 |
| 1M | 999,988 | 8,760 | 56 | 69 |
| 2M | 1,999,743 | 17,699 | 110 | 73 |

Early cuts have fewer questions because some families are not askable yet.

### Verdicts

| Verdict | Meaning |
| --- | --- |
| `right` | the expected answer; for a never-told question, a decline that does not then guess |
| `wrong` | something else, a look-alike's value, or code or a page that fails its checks |
| `stale` | a value an update replaced, the uncorrected method's number, or the old main colour |
| `declined` | says it doesn't know, but the answer was told |
| `false_memory` | answers a question about something never told, or declines and then guesses |

The same answer always gets the same verdict. Grading costs nothing, and anyone can grade again.

### Build it and look at it

```sh
.venv/bin/python -m engram.bench.haul build --seed 1 --out work/haul/s1
.venv/bin/python -m engram.bench.longhaul show --dir work/haul/s1
.venv/bin/python -m engram.bench.haul sample --n 15 --per-family --cut 1M --dir work/haul/s1
.venv/bin/python -m engram.bench.haul grade --dir work/haul/s1 --answers answers.jsonl --cut 1M [--browser]
```

- `build` writes `script.jsonl` (one event per line), `probes.jsonl` (one probe per line) and `manifest.json`
  (counts per family, and tokens and askable probes per cut).
- `grade` reads lines of `{"id": ..., "answer": ...}`. `--browser` also loads page answers in a headless Chromium
  (`$HAUL_BROWSER`, or one installed in the usual places).

### Scoring any contender

Two functions in `engram.bench.longhaul` are shared by every contender:

```python
checkpoints(folder: Path, cuts: dict[str, int] = CUTS, per_family: int = PER_FAMILY,
            seed: int = SAMPLE_SEED) -> tuple[list[dict], list[dict]]
grader(question: dict, answer: str) -> dict
```

- `checkpoints` returns the events and the checkpoints. A checkpoint is `{name, tokens, events, questions}`.
  `events` is how many events are told by then. Each question is `{id, question, expected, family, probe}`.
- `grader` returns `{verdict, right, reason}` for one answer.

The local runners use the contender protocol in `engram.bench.contender`: a contender is told the history one event
at a time (`tell(text, day)`) and asked questions (`ask(question, *, max_tokens, family)`). Answers get room by
family: 1,200 tokens for a page, 600 for code, 400 for maths and 120 for the rest. Qwen3's thinking is off for every
local model.

### The contenders by name

| Name | Runner | What it is |
| --- | --- | --- |
| `engine:<model>` | `engram.bench.local` | the engine: one project reach's memory, driven as `Session` drives it, with the vault, the core, the tiers and the metrics on; 2 GB of RAM for hot rooms and 40 GB of disk for room files; `qwen3-1.7b`, `qwen3-4b` or `qwen3-8b`. Questions are read-only (`--learn` to change that); `--wake` wakes an asleep room instead of reading it as words; `--wording own` gives every local contender the engine's own instructions (names end `+own`) |
| `words:<model>` | `engram.bench.local` | the engine's rooms, chosen the same way, pasted in as text; for `qwen-27b` |
| `bare:<model>` | `engram.bench.local` | no memory: the most recent part of the history that fits (32K tokens for the 1.7B and 8B, 64K for the 4B, 16K for the 27B, so their keys and values fit in 24 GB) |
| `ollama:<model>` | `engram.bench.ollama_run` | Ollama through the pairing: memory as words |
| `ollama-bare:<model>` | `engram.bench.ollama_run` | plain Ollama, with the most recent 32,768 tokens of the history in its prompt |
| `claude-<model>` | `engram.bench.longhaul`, `engram.bench.suite_run` | Claude alone, the yardstick |

The engine's moments carry their date and the Long Haul's day number, as `[YYYY-MM-DD, day 50] text`, since the
Long Haul asks about days by number.

### Rerun it

```sh
# the engine and the other local contenders, through MLX
.venv/bin/python -m engram.bench.local longhaul --contender engine:qwen3-1.7b --dir work/haul/s1
.venv/bin/python -m engram.bench.local longhaul --contender bare:qwen3-1.7b --dir work/haul/s1 --cuts 64K 256K

# the wait as the memory grows, during one reading of the Long Haul: points at 1K and 10K moments, and the end
.venv/bin/python -m engram.bench.local speed --contender engine:qwen3-1.7b --dir work/haul/s1

# Ollama, paired and bare
.venv/bin/python -m engram.bench.ollama_run longhaul --contender ollama:qwen3-1.7b --dir work/haul/s1
.venv/bin/python -m engram.bench.ollama_run longhaul --contender ollama-bare:qwen3-1.7b --dir work/haul/s1

# Claude, alone
.venv/bin/python -m engram.bench.longhaul claude --model claude-haiku-5-5 --dir work/haul/s1
.venv/bin/python -m engram.bench.longhaul claude --model claude-sonnet-5-5 --dir work/haul/s1 --cuts 64K 256K
```

For the local and Ollama runners, `--limit N` asks at most N questions per checkpoint, every family in turn: a
quick check before a full run.

Each run writes a dated record after every checkpoint, to
`records/bench/<YYYY-MM-DD>/<HHMMSS>-<task>-<contender>.json`. Memories made by a run go under `work/memories/`.

## The Claude yardstick

- Claude reads the history as text: the most recent part that fits its 1M-token window, with room for the
  questions and the reply. A long history is cut from the front.
- All three models get the same settings: effort "medium" and adaptive thinking. Thinking cannot be turned off on
  Opus 5.5; it is billed and recorded as output.
- A checkpoint's questions go in one request, which asks for the answers as JSON. The history is cached where the
  last request ended, so later checkpoints read it from the cache.
- A reply cut off by its own `max_tokens` is not graded wrong. The questions it never reached are asked once more,
  alone, with twice the room.
- Every request streams, so the time to the first token is exact. A stream is one try: the SDK's own retries are
  off for it, so no retry wait counts as time to the first word.
- No fallback model is ever asked for, so each record names the model that answered. A refusal is recorded as a
  refusal.

**Cost.** Every call logs its tokens and its cost at list price in `records/bench/claude-ledger.jsonl`. The ledger
holds a hard cap of $60 for the night. Before a call is sent, its worst case is held in the ledger, and the call is
refused if that would pass the cap less $2 of headroom.

| Model | Input | Output | Cache read | Cache write (5 minutes) |
| --- | --- | --- | --- | --- |
| `claude-opus-5-5` | $4 | $20 | $0.20 | 1.25 × input |
| `claude-sonnet-5-5` | $2 | $10 | $0.20 | 1.25 × input |
| `claude-haiku-5-5` | $0.10, or $0.50 past 100K | $0.50, or $2.50 past 100K | 0.1 × input | 1.25 × input |

Prices are per million tokens. A Haiku prompt over 100K tokens is priced on its long card for every token of that
call.

```sh
.venv/bin/python -m engram.bench.claude smoke    # one tiny call
.venv/bin/python -m engram.bench.claude spent    # what the ledger has spent, against the cap
```

**The key.** It is read from `~/.config/camr/anthropic.env` when the client is made, and handed straight to it. It
is never printed, logged or stored.

## The Hugging Face suites

Public benchmarks, loaded, sampled with a seed and graded by their own rules (`engram.bench.suites`).

| Suite | Source | What it tests | Graded by | `--n` counts |
| --- | --- | --- | --- | --- |
| `babilong` | RMT-team/babilong | bAbI facts hidden in book text, qa1 to qa5, at 4k to 1M tokens | the dataset's own rule | items per task, each story at every length |
| `memoryagentbench` | ai-hyz/MemoryAgentBench | Conflict_Resolution and Accurate_Retrieval: one long context fed in chunks, then many questions | exact match after normalising | questions per context |
| `math500` | HuggingFaceH4/MATH-500 | 500 competition problems | the last `\boxed{}` answer, by value with sympy | problems |
| `aime` | MathArena/aime_2025 and aime_2026 | 30 problems a year, each a whole number 0 to 999 | exact | problems per year |
| `harp` | aadityasingh/HARP | correction pairs: problem A and its worked solution as context, then a new problem B of the same subject and level | by value, in HARP's own order of checks | pairs |
| `longmemeval` | xiaowu0162/longmemeval-cleaned, S set | 500 questions, each over about 50 chat sessions (about 115K tokens); 30 about things never said | a judge model (Claude Haiku 5.5), by the benchmark's rules | questions per kind |
| `webdev` | lmarena-ai/leaderboard-dataset | how models got better at building web pages: the WebDev rating history | not graded: a CSV and a summary | |

Every item has `id`, `suite`, `context` (the text, or its chunks in order), `question`, `answer`, `length_tokens`
and `meta`. A verdict is `right`, `wrong` or `declined`; for questions about things never said, `right_abstain` or
`false_memory`.

```sh
.venv/bin/python -m engram.bench.suites list
.venv/bin/python -m engram.bench.suites sample babilong --n 2 --seed 0 --lengths 4k,16k
.venv/bin/python -m engram.bench.suites webdev
```

### Rerun them

`engram.bench.suite_run` runs a suite against any contender: the engine, Ollama (paired or bare), or Claude with no
memory. Each context gets a memory of its own.

| Suite | How it is run |
| --- | --- |
| `babilong` | qa1 to qa5 at 4k, 16k, 64k and 128k, plus 256k, 512k and 1M for Claude; the story is told in chunks of about 512 tokens, then its question is asked |
| `memoryagentbench` | Conflict_Resolution: each context's chunks in order, then its questions |
| `math500` | 50 problems of levels 3 to 5, no memory: what the model can do on its own |
| `aime` | AIME 2025 and 2026, no memory |
| `harp` | memory on: problem A and its worked solution are told, then 30K tokens of Long Haul noise, then problem B and A again are asked; memory off: B and A with nothing told |

```sh
.venv/bin/python -m engram.bench.suite_run babilong --contender ollama-bare:qwen3:1.7b --n 3 --lengths 4k
.venv/bin/python -m engram.bench.suite_run harp --contender ollama:qwen3-1.7b --n 20
.venv/bin/python -m engram.bench.suite_run math500 --contender claude-haiku-5-5 --n 50 --max-usd 10
```

The suites run Claude and Ollama contenders. The engine's MLX contenders are not run on them yet: their instructions are the Long Haul's, and a suite needs its own.

A Claude run prints its estimated cost first, and does not start when that passes `--max-usd` (10 by default).
`--estimate` prints the estimate and stops. Every Claude call is also held in the ledger against the night's cap.

`suite_run` does not run `longmemeval` or `webdev`. LongMemEval needs its judge model; its loader and judge prompts
are in `engram.bench.suites.longmemeval`. WebDev Arena is a history, not questions.

From Python:

```python
from engram.bench import suites

items = suites.sample("babilong", 2, seed=0, lengths=["4k", "16k"])
for item in items:
    for chunk in item.chunks:
        ...  # tell the contender
    reply = ...  # ask it suites.prompt(item)
    verdict = suites.grade(item, reply)
```

```python
suites.load(suite: str, **kw) -> list[Item]
suites.sample(suite: str, n: int, seed: int = 0, **kw) -> list[Item]
suites.prompt(item: Item) -> str
suites.grade(item: Item, reply: str, judge: Callable[[str], str] | None = None) -> str
```

Downloads are kept in `$ENGRAM_DATASETS`, or else in the ignored `work/datasets/`. Once a file is there, no network
is needed.

## Speed

How the wait grows with memory on the desk, notes against words, with the SSD read and the cache bypassed:

```sh
.venv/bin/python -m engram.ruler speed --persona student
```

How fast each local model reads and writes on this Mac, from 512 to 32K tokens, through MLX and through Ollama:

```sh
.venv/bin/python -m engram.bench.throughput --out records/bench
```

## The ruler: the scripted lives

The step 0 to step 2 measurements use three scripted 12-week lives (a student, a dairy-cooperative manager and a
developer) and the same 100-question quiz every week.

```sh
scripts/step1.sh     # every contender through the three held-out lives
scripts/errands.sh   # errands for every contender and life
.venv/bin/python -m engram.ruler run --persona student --seed 1 --contender engram
```

Seed 1 is for the proof. Seed 0 is for development and tuning.

## Results

Measured on the MacBook Pro M5 Pro (24 GB), 4 November 2026. The records are in `records/bench/2026-11-04/`.

Right answers on the Long Haul (34, 40, 69 and 73 questions at 64K, 256K, 1M and 2M; 3M and 4M ask the 2M questions
on the longer script):

| Contender | 64K | 256K | 1M | 2M | 3M | 4M | First word p50 | Peak RAM |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `engine:qwen3-4b` | 25 | 26 | 25 | 29 | 29 | 29 | 0.21–0.31 s | 6.3 GB MLX peak; 7.5 GB process, capped |
| `bare:qwen3-4b` | 18 | 14 | 20 | 11 | 12 | 13 | 0.32–0.38 s | 14.7 GB MLX peak; 15.2 GB process |
| `engine:qwen3-8b` | 26 | 26 | 24 | 27 | | | 0.32–0.54 s | 8.0 GB MLX peak; 8.1–8.8 GB process |
| `bare:qwen3-8b` | 15 | 11 | 15 | 11 | | | 0.22 s | 12.2 GB MLX peak; 13.6 GB process |
| `engine:qwen3-1.7b+own` | 19 | 20 | 21 | 21 | | | 0.10–0.14 s | 4.5 GB |
| `engine:qwen3-1.7b` | 14 | 20 | 17 | 15 | | | 0.10–0.14 s | 4.5 GB |
| `bare:qwen3-1.7b+own` | 7 | 7 | 14 | 9 | | | 0.13 s | 7.5 GB |
| `bare:qwen3-1.7b` | 8 | 13 | 14 | 7 | | | 0.13 s | 7.5 GB |
| `ollama:qwen3:1.7b` | 16 | 17 | 16 | 16 | | | 0.38–0.40 s | 3.3 GB |
| `ollama-bare:qwen3:1.7b` | 8 | 12 | 10 | 7 | | | | 5.7 GB |
| `claude-haiku-5-5` | 22 | 21 | 17 | 10 | 10 | 10 | 13–43 s | |
| `claude-sonnet-5-5` | 28 | 35 | 43 | 32 | 13 | 10 | 13–53 s | |
| `claude-opus-5-5` | 24 | 33 | 42 | 31 | | | 19–105 s | |

The 8B and the 27B are in the records once their runs finish.

The Hugging Face suites (right answers):

| Suite | `claude-haiku-5-5` | `claude-sonnet-5-5` |
| --- | --- | --- |
| MATH-500, levels 3 to 5 (50) | 44 | 47 |
| AIME 2025 and 2026 (60) | 54 | 56 |
| HARP pairs, memory on (60) | 55 | 58 |
| HARP pairs, memory off (60) | 48 | 52 |
| BABILong qa1–qa5, 4k to 128k (100) | 78 | |

The wait as the engine's memory grows (`engram.bench.local speed`, `engine:qwen3-1.7b`):

| Moments kept | History | First word, p50 | Retrieval, p50 | Peak RAM | Disk |
| --- | --- | --- | --- | --- | --- |
| 1,000 | 112K tokens | 0.11 s | 24 ms | 4.26 GB | 14.9 GB |
| 10,000 | 1.15M tokens | 0.15 s | 17 ms | 4.28 GB | 40.0 GB |
| 17,676 (the end of the Long Haul) | 2.01M tokens | 0.08 s | 18 ms | 4.23 GB | 40.1 GB |

Notes read off the SSD at 6–12 GB/s when a room is not hot. At 2M most rooms are asleep (4,471 of 5,391), so most
answers read their room as words, and read nothing from the SSD.

The records are under `records/bench/`. Each names the machine, how busy it was (`load_1m`), and the code that made
it (`engram_source_sha`).

## Rules for measuring

- One measuring job at a time. The GPU runs one model, and anything else running skews the times.
- A record is made by the code it names. A change to the code means a new record.
- Claude's spending is held under the ledger's cap, call by call.
