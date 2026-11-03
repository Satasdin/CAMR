# Overnight build plan, 4 Nov 2026

This is the source of truth for tonight's work. The reviewed plan lives in the shared doc "The Lightweight Memory
Engine — project plan" (https://claude.ai/artifact/4EsHPLGikBK8A6chtqbQLj), main tab and Benchmarks tab. This file
condenses it for the agents building in this worktree.

## The project in one line

A **lightweight external memory engine** for local language models on a Mac: memory the model reads like its own
weights, swapped between the SSD and RAM by what the task needs. The app and the benchmarks only show it and prove it.
The thesis title stands: "A Lightweight External Memory Engine to Bridge the Capability Gap Between On-Device and
Cloud Language Models".

## Decided (Ibrahim, 4 Nov)

- **Not a vector database.** Memory is tensors the model reads directly. People browse it as an Obsidian-like vault.
- **Three layers:**
  - **subconscious:** an always-on core in RAM;
  - **conscious:** rooms of saved keys and values on the SSD, burst-read onto the desk;
  - **archive:** the vault of linked plain-text notes.
- **Local only.** The engine serves models running on this Mac (MLX). There are no plugins for Claude Code, Codex or
  LM Studio. The one exception is a test of pairing with Ollama's CLI and app; through Ollama, memory goes in as text.
- **Claude is only a yardstick.** It answers the same tasks on its own, with no memory. Every Claude call logs its
  tokens and cost. Hard cap for the night: **$60** total. The key is in `~/.config/camr/anthropic.env`; read it at
  runtime only and never print, log or commit it.
- **The name is not chosen yet.** The code stays in package `engram` under `v2/` until he picks one.

## What exists (CAMR v2, `v2/engram/`)

| File | What it does |
| --- | --- |
| `notes.py` | Turns tokens into KV "notes" with Qwen3 through MLX. Lays the desk. Turns keys (RoPE) when needed. |
| `rooms.py` | Append-only room files on the SSD (at most 512 tokens each, join at 0.80), read with F_NOCACHE in one burst. Holds `index.json` and `vectors.npy`. |
| `memory.py` | `remember`, `choose`, `recall`, `answer`. The desk is one room plus the 4 closest moments as words. |
| `events.py` | Watches attention at layers 12/16/20/24. A moment is "used" at a share ≥ 0.10. Writes `events.jsonl`. |
| `agent.py` | Ten pretend tools and one tool call. Its parser reads Qwen3 JSON and Qwen 3.5+ XML tool calls. |
| `models.py` | `READER` Qwen3-1.7B-4bit, `READER_BIG` 4B, `READER_27B`, `EMBEDDER` Qwen3-Embedding-0.6B. Generation reports TTFT and tok/s. |
| `ruler/` | Scripted lives, grading by rule, dated JSON records, the speed test, charts. |
| `app/` | Local server on 127.0.0.1:8765 (Host, Origin, JSON-only and launch-token checks) and one static page. |

Measured on this MacBook Pro M5 Pro (24 GB):
- 0.07 s to the first word, flat as memory grows;
- 1.65–1.83 GB peak RAM;
- Qwen 27B with memory got 62–68 of 85 on the quiz, against 0 without.

Saved notes are 112 KB per token on the 1.7B, about 29,000× the text. That is why sleep and the archive exist.

## Rules for every agent tonight

1. **Work only inside `/Users/p3wrky/Desktop/camr-build-wt`**, using absolute paths.
   - Never touch `/Users/p3wrky/Desktop/camr-repo`: it holds Ibrahim's uncommitted work.
   - Never touch `/Users/p3wrky/Developer/engram`.
2. **Stay in your own directory.** Each agent writes only the paths its brief names. Shared files (`pyproject.toml`,
   `README.md`, `DECISIONS.md`) are changed only by the lead.
3. **Do not commit or push.** The lead commits after each phase.
4. **Never load an MLX model or run a benchmark unless your brief says so.** The GPU runs one measuring job at a
   time, and that job belongs to the lead. Unit tests must not load models: use fakes.
5. **Python** runs from `/Users/p3wrky/Desktop/camr-build-wt/v2/.venv/bin/python`. Run tests with
   `cd /Users/p3wrky/Desktop/camr-build-wt/v2 && .venv/bin/python -m pytest -q`. The existing tests must stay green.
6. **Keep measured behaviour.** Do not change what `notes.py`, `rooms.py`, `memory.py` or `events.py` compute today.
   Add to them with new options that default to today's behaviour.
7. **Match the house style:** short docstrings in plain words, as in the existing modules, and type hints.
8. **Secrets:** no keys, tokens or personal data in files, logs or output. The repo is public.

## Metrics on every answer

These go into every record:
- right or wrong;
- honest (declined what was never told) and false memory;
- time to the first word and total time;
- prefill tok/s and decode tok/s;
- retrieval ms (choose, SSD read, laying the desk; p50 and p90);
- bandwidth: bytes read from the SSD, GB/s, and its share of the wait;
- context tokens used, against the history's total tokens;
- peak RAM and disk;
- for Claude: input, cached and output tokens, and $ at list price.

Claude list prices per million tokens:

| Model | Input | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- |
| `claude-opus-5-5` | $4 | $20 | $0.20 | 1.25× input |
| `claude-sonnet-5-5` | $2 | $10 | $0.20 | 1.25× input |
| `claude-haiku-5-5` | $0.10, or $0.50 past 100K | $0.50, or $2.50 past 100K | — | — |

## The Long Haul (our own hard test)

- One scripted project: a developer building "Mama Njeri's Kitchen" (Nairobi), its site and back office, over 110
  working days. It is deterministic from a seed.
- It mixes chat, decisions, code, a maths course and noise.
- It is cut at 64K, 256K, 1M and 2M tokens.
- Probes are planted early and asked late, each with one answer a rule can check:

| Probe | Planted | Asked | Graded |
| --- | --- | --- | --- |
| Facts across the gap | 400 facts at random depths | Recall far past every window | Exact |
| Changed facts | 80 facts changed 2–4 times, with dates | Value now; value on a past date | Exact; stale counted |
| Two-hop links | Halves weeks apart | Needs both | Exact |
| Corrected maths | 40 hard problems; a step-by-step correction follows whatever the model answers; some use an invented project rule | Same problem; same method, new numbers; invented rule on a new case | Exact number |
| The page that grows | Design system in week 1; main colour changes on day 61 | "Build the catering page" on day 110 | HTML/CSS checks; loads in a headless browser |
| Code that must fit | Helpers with exact names, units, quirks | New code calling them | Unit tests run on the answer |
| Look-alikes | Two Wanjirus, prices 1 shilling apart, near-identical repo names | Aimed at one of each pair | Exact |
| Never said | 60 questions on things never told | Same | A decline is right; a guess is a false memory |

Sample items, with their expected answers, are in the doc's Benchmarks tab. One example: the fee rule is 1% rounded
up to the next 5 shillings, at least 10, and a flat 25 for exact multiples of 1,000. So 12,000 gives 25 and 7,321
gives 75.

## Who runs what

| Model | Runtime | Memory as |
| --- | --- | --- |
| Qwen3 1.7B, Qwen3 4B Instruct 2507, Qwen3 8B | MLX 4-bit | Tensors (rooms + core) and the vault |
| Qwen 27B (`mlx-community/Qwen3.8-27B-4bit`) | MLX 4-bit | Words: its linear-attention layers keep no KV to save |
| Qwen3 1.7B, 4B, 8B | Ollama, through the pairing proxy | Words |
| Claude Haiku 5.5, Sonnet 5.5, Opus 5.5 | API | None: the yardstick |

## Layout tonight

| Path | What lives there |
| --- | --- |
| `v2/engram/vault.py`, `reach.py`, `core.py`, `swap.py`, `metrics.py` | New engine layers |
| `v2/engram/bench/` | Long Haul generator, graders, runners (local, Claude, Ollama), Hugging Face suites |
| `v2/engram/pair/` | Ollama pairing proxy |
| `v2/engram/app/` | The app (rebuilt after the design pick) |
| `v2/design/` | Design research and the chosen direction |
| `v2/records/bench/` | Benchmark records (dated JSON) |
| `v2/docs/` | Docs for people, plus `llms.txt` for agents |
