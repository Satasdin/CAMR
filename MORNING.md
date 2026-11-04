# Good morning — what happened overnight (4 Nov 2026)

Branch `camr-build` on Satasdin/CAMR. Everything below is committed and pushed. Nothing is merged into the default
branch.

## In one breath

<!--HEADLINE-->

## The engine, the app and the proof: what exists now

**The engine** (`v2/engram/`):
- **Subconscious:** `core.py`, an always-on core in RAM.
- **Conscious:** `rooms.py` + `swap.py`. Rooms of saved keys and values on the SSD, the hot ones kept in RAM, the
  cold ones put to sleep under a disk budget.
- **Archive:** `vault.py`, linked plain-text notes you can browse like an Obsidian vault.
- **Reach:** `reach.py`, for session, project, agent or global memory.
- **Metrics:** `metrics.py`, every answer's speed, retrieval and bandwidth.

**The app** (`python -m engram.app`): six screens in the "Instrument" design you picked. Screenshots are in
`v2/docs/screens/`.

| Screen | What it does |
|---|---|
| Models | What fits this Mac (from measured speeds), Hugging Face search and download, MLX and Ollama |
| Chat | Memory on/off per session, reach picker, the stage showing SSD → RAM → desk as each answer is made |
| Code | A Claude Code–style agent on your local model: personas, tools, MCP servers, skills, a gated shell |
| Swarm | 1–8 agents, each with its own memory, sharing one RAM budget |
| Memory | The microscope: every room as a tensor tile, the bus, the RAM ruler, the vault; replays any answer |
| Bench | Every record, live: score against history, first word, peak RAM, and Claude's spend |

**The pairing:** `engram.pair.ollama` is a proxy that gives Ollama's CLI and app memory as words.

**The proof:**
- `engram/bench/`: the Long Haul (our own test), the local, Ollama and Claude runners, and the Hugging Face suites.
- Records: `v2/records/bench/2026-11-04/`.
- Decisions: `v2/DECISIONS.md` E-29 to E-38.

**The docs:** `v2/docs/site/` for people, and `v2/llms.txt` / `llms-full.txt` for agents.

**Tests:** <!--TESTS--> pass.

## The Long Haul: one project, 110 days, 2.01M tokens, 216 questions

<!--LONGHAUL-->

## Speed as memory grows (1.7B engine)

| History told | First word p50 | Retrieval p50 | Peak RAM | Disk |
|---|---|---|---|---|
| 112K tokens (1K moments) | 0.11 s | 24 ms | 4.26 GB | 14.9 GB |
| 1.15M tokens (10K moments) | 0.15 s | 17 ms | 4.28 GB | 40.0 GB (budget) |
| 2.01M tokens (17.7K moments) | 0.08 s | 18 ms | 4.23 GB | 40.1 GB (budget) |

Claude's first token on the same history takes 13–105 s.

Model throughput on this Mac (MLX, 512 → 32K tokens):

| Model | Reading (tok/s) | Writing (tok/s) | Notes |
|---|---|---|---|
| 1.7B | 6,170 → 3,170 | 220 → 56 | |
| 4B | 2,510 → 1,180 | 101 → 36 | |
| 8B | 1,315 → 845 | 57 → 29 | |
| 27B | 360 → 372 | 17.6 | does not fit 32K |

Ollama reads 3–5× slower than MLX.

## Hugging Face suites

<!--SUITES-->

## What I found that you should know

<!--FINDINGS-->

## What is not done

<!--NOTDONE-->

## Your calls (taste and vision only)

1. **The name.** The code still says `engram` and the repo says CAMR. Pick one and I'll rename both.
2. **Three small design choices** at the end of `v2/design/DIRECTION.md`:
   - amber or ember for RAM;
   - a flat or a layered stage;
   - Martian Mono or IBM Plex for numbers.
3. **Old branches.** Can I delete `camr-unify` and `Satasdin/camr-overnight-e82a88` on GitHub?
4. **Rotate the Anthropic key** you pasted into chat. It was only ever read from `~/.config/camr/anthropic.env` and
   never written anywhere else, but it was in a chat.

## Look at it

```bash
cd ~/Desktop/camr-build-wt/v2 && .venv/bin/python -m engram.app --open
```

That loads the 1.7B. Ask something in Chat (key `2`), then watch Memory (key `5`). Bench (key `6`) has every number
in this file.
