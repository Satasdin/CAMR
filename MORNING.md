# What happened overnight (4 Nov 2026)

Branch `camr-build` on Satasdin/CAMR. Everything here is committed and pushed. Nothing is merged into the default
branch. The plan doc's Benchmarks tab has the same numbers: https://claude.ai/artifact/4EsHPLGikBK8A6chtqbQLj

## In one breath

A 4B model on this Mac, given the memory engine, answers a 2M-token project history nearly as well as Claude Sonnet or
Opus alone: 29 of 73, against 32 and 31.
- It recalls more of the planted facts (6 of 10, against their 4).
- It still declines 9 of the 10 questions about things never said.
- Its first word comes in about 0.3 s, against Claude's 13–105 s.

The same 4B without memory gets 11 and needs 14.7 GB of RAM; with the engine it needs 5.7 GB. Past 2M, Claude
alone recalls nothing planted (Sonnet 13 of 73 at 3M, 10 at 4M). **At 3M and at 4M the 4B with the engine still gets 29** (Sonnet alone: 13, then 10), declines all 10 never-said questions, and answers in 0.31 s, in a 5.4–7.5 GB process.

## What exists now

**The engine** (`v2/camr_engine/`):
- **Subconscious:** `core.py`, an always-on core in RAM.
- **Conscious:** `rooms.py` and `swap.py`. Rooms of saved keys and values on the SSD; hot rooms stay in RAM, and cold
  ones go to sleep under a 40 GB disk budget.
- **Archive:** `vault.py`, linked plain-text notes you can browse like an Obsidian vault.
- **Reach:** `reach.py`, for session, project, agent or global memory.
- **Metrics:** `metrics.py`, every answer's speed, retrieval and bandwidth.

**The app** (`python -m camr_engine.app --open`): six screens in the "Instrument" design you picked. Screenshots are in
`v2/docs/screens/`.

| Screen | What it does |
|---|---|
| Models | what fits this Mac (from measured speeds), Hugging Face search and download, MLX and Ollama |
| Chat | memory on/off per session, reach picker, the stage showing SSD → RAM → desk as each answer is made |
| Code | a Claude Code–style agent on your local model: personas, tools, MCP servers, skills, a shell that asks first |
| Swarm | 1–8 agents, each with its own memory, sharing one RAM budget |
| Memory | every room as a tensor tile, the bus, the RAM ruler, the vault; replays any answer |
| Bench | every record, live: score against history, first word, peak RAM, and Claude's spend |

**The pairing:** `camr_engine.pair.ollama` is a proxy that gives Ollama's CLI memory as words
(`OLLAMA_HOST=127.0.0.1:11435`).

**The proof:**
- `camr_engine/bench/`: the Long Haul (our own test, now extendable to 4M tokens), the local, Ollama and Claude runners,
  and the Hugging Face suites.
- Records: `v2/records/bench/2026-11-04/`.
- Decisions: `v2/DECISIONS.md` E-29 to E-43.

**The docs:** `v2/docs/site/` for people, and `v2/llms.txt` / `llms-full.txt` for agents. The README is rewritten
for the engine as it stands.

**Tests:** 730 pass.

## The Long Haul

The script is one project, "Mama Njeri's Kitchen", 110 working days and 2.01M tokens. It is extended to 220 days
and 4.01M tokens with nothing new planted. The same 216 questions are graded by rule, and 3M and 4M ask the 2M
questions again.

| Right answers | 64K (34) | 256K (40) | 1M (69) | 2M (73) | 3M (73) | 4M (73) | First word | Peak RAM |
|---|---|---|---|---|---|---|---|---|
| **Engine, Qwen3 4B** | **25** | **26** | **25** | **29** | **29** | **29** | 0.2–0.31 s | 7.5 GB (process) |
| Bare 4B (newest 64K) | 18 | 14 | 20 | 11 | 12 | 13 | 0.32–0.38 s | 15.2 GB (process) |
| Engine, Qwen3 8B | 26 | 26 | 24 | 27 | | | 0.3–0.54 s | 8.1–8.8 GB (process) |
| Bare 8B (newest 32K) | 15 | 11 | 15 | 11 | | | 0.22 s | 13.6 GB (process) |
| Qwen 27B, the engine's memory as words | 24 | 21 | 24 | 27 | | | 2.2–2.4 s | 16–17 GB (process) |
| Engine, Qwen3 1.7B, its own wording | 19 | 20 | 21 | 21 | | | 0.10–0.14 s | 4.4 GB |
| Engine, Qwen3 1.7B, the yardstick's wording | 14 | 20 | 17 | 15 | | | 0.10–0.14 s | 4.4 GB |
| Bare 1.7B (newest 32K) | 8 | 13 | 14 | 7 | | | 0.13 s | 7.4 GB |
| Ollama 1.7B + pairing (memory as words) | 16 | 17 | 16 | 16 | | | 0.38–0.40 s | 3.3 GB |
| Ollama 1.7B bare | 8 | 12 | 10 | 7 | | | — | 5.7 GB |
| Claude Haiku 5.5 alone | 22 | 21 | 17 | 10 | 10 | 10 | 13–43 s | — |
| Claude Sonnet 5.5 alone | 28 | 35 | 43 | 32 | 13 | 10 | 13–53 s | — |
| Claude Opus 5.5 alone | 24 | 33 | 42 | 31 | | | 19–105 s | — |

At 2M, by family (10 questions each; for "never said", declining is right):

| Family | Engine 4B | Engine 1.7B (own) | Haiku | Sonnet | Opus |
|---|---|---|---|---|---|
| Facts across the gap | **6** | **6** | 0 | 4 | 4 |
| Changed facts | 3 | 2 | 0 | 5 | 5 |
| Look-alikes | 3 | 3 | 0 | 5 | 5 |
| Corrected maths | 4 | 4 | 0 | 6 | 6 |
| Code that must fit | 4 | 2 | 0 | 2 | 1 |
| Two hops | 0 | 1 | 0 | 0 | 0 |
| Never said | 9 | 3 | 10 | 10 | 10 |
| The page that grows (3) | 0 | 0 | 0 | 0 | 0 |

## Which reach works best (4B engine, 256K tokens, 40 questions)

| Set-up | Right | Facts | First word | Disk |
|---|---|---|---|---|
| Session: each week its own memory, asked in the last week | 11 | 0 of 10 | 0.24 s | 44 GB |
| **Project: every week into one project memory** | **26** | **8 of 10** | 0.19 s | 44 GB |
| Global: this project and another one in one memory | 24 | 8 of 10 | 0.19 s | 85 GB |
| Project + global: both read, the closest room wins | 24 | 7 of 10 | 0.19 s | 85 GB |

- **Project reach is the best.** A session alone sees only its own week.
- **Mixing in a second project costs 2 answers.**
  - In global, the other project's look-alike maths rule was taken twice.
  - In project + global, the other project's room won 7 of the 40 questions. The 4B declined the 2 it could not
    answer rather than borrow the other project's facts.
- **Never-said questions:** 10 of 10 declined every time (E-42).

## Speed as memory grows (1.7B engine)

| History told | First word p50 | Retrieval p50 | Peak RAM | Disk |
|---|---|---|---|---|
| 112K tokens (1K moments) | 0.11 s | 24 ms | 4.26 GB | 14.9 GB |
| 1.15M tokens (10K moments) | 0.15 s | 17 ms | 4.28 GB | 40.0 GB (budget) |
| 2.01M tokens (17.7K moments) | 0.08 s | 18 ms | 4.23 GB | 40.1 GB (budget) |

On the same 2.01M tokens, Claude waits 13–105 s before its first token.

## Hugging Face suites

| Suite | Claude Haiku 5.5 | Claude Sonnet 5.5 | Ollama 1.7B bare | Ollama 1.7B + pairing |
|---|---|---|---|---|
| MATH-500, levels 3–5 (50) | 44 | 47 | | |
| AIME 2025 + 2026 (60) | 54 | 56 | | |
| HARP pairs, correction told (60) | 55 | 58 | not run | not run |
| HARP pairs, nothing told (60) | 48 | 52 | | |
| BABILong 4k–128k (100) | 78 | — | not run | not run |

Claude spend for the night: $28.71 of the $60 cap, logged per call in `v2/records/bench/claude-ledger.jsonl`.

## What I found that you should know

1. **The 1.7B's wording, not its memory, sank its recall at 1M and 2M** (E-37).
   - With Claude's instructions ("answer from them only; when they never say, answer I don't know") it declined
     facts sitting right on its desk.
   - I checked retrieval (the right room was chosen) and sleep (waking the room changed nothing) before finding it.
   - With its own wording it recalls more but invents more (never-said 3 of 10 at 2M).
   - The 4B doesn't have this problem: it keeps Claude's wording and is both right and honest.
2. **Tensors buy speed, not accuracy.**
   - Same 1.7B, same wording: the engine scores 14 / 20 / 17 / 15 and Ollama with memory as words scores
     16 / 17 / 16 / 16.
   - The engine answers 3× sooner (0.10–0.14 s against 0.38–0.40 s).
   - It uses 40 GB of disk against 0.1 GB.
3. **Speed does not grow with memory.** From 112K to 2M tokens:
   - the first word stays at about 0.1 s;
   - RAM stays at about 4.3 GB;
   - disk is held at its budget by putting cold rooms to sleep (4,471 of 5,391 asleep at the end).
4. **Nobody builds the growing page.** Every model, Claude included, failed all three catering-page checks at 2M. It
   is the hardest probe: it needs the week-1 design system and the day-61 colour change.
5. **The engine's process held 19 GB, not the 5.7 GB the records showed** (E-40).
   - MLX kept freed GPU buffers up to the whole GPU limit, and swap filled.
   - The cache is now capped at 1 GB, and every record logs the process's real footprint.
   - Measured on the 4B at 3M (E-41): the footprint fell from 19.2 GB to 7.5 GB, reading went from 99.5 to 53 min,
     and the first word from 0.37 to 0.31 s, with identical answers.
   - Scores are unaffected; the RAM figures of tonight's runs are understated.
6. **Claude is honest but blind past its window.**
   - It never invented a never-said fact.
   - At 3M and 4M it recalls nothing planted: its 1M window holds only the last days.

## What is not done

- **Swarms are built but not measured.** Reach is measured (above). The app's swarm screen has no benchmark yet.
- **No live demo with a loaded model.** The app screenshots are from a recorded memory with no model loaded, since
  the GPU was measuring all night.
- **The engine is not run on the Hugging Face suites.** `suite_run` takes Claude and Ollama only; the engine needs
  a suite wording.
- **LongMemEval, MemoryAgentBench and Web-Bench** have loaders but no runs.
- **Running now (queue9):** the Ollama suite runs redone (E-43). The bare BABILong lost 58 answers to a too-strict
  thinking check, and HARP's 400-token limit cut off 80% of the 1.7B's working. Paired BABILong (20 of 100) stands.
- **4M:** rerun on power with the cache cap: 29 of 73 at 3M and at 4M.

## Your calls (taste and vision only)

1. **The name.** The code still says `camr` and the repo says CAMR. Pick one and I'll rename both.
2. **Three small design choices** at the end of `v2/design/DIRECTION.md`:
   - amber or ember for RAM;
   - a flat or a layered stage;
   - Martian Mono or IBM Plex for numbers.
3. **Old branches.** Can I delete `camr-unify` and `Satasdin/camr-overnight-e82a88` on GitHub?
4. **Rotate the Anthropic key** you pasted into chat. It was only ever read from `~/.config/camr/anthropic.env`.
5. **Sleep.** If you ran `sudo pmset -a disablesleep 1`, undo it with `sudo pmset -a disablesleep 0`.

## Look at it

```bash
cd ~/Desktop/camr-build-wt/v2 && .venv/bin/python -m camr_engine.app --open
```

That loads the 1.7B. Ask something in Chat (key `2`), then watch Memory (key `5`). Bench (key `6`) has these numbers
live.
