# What happened overnight (4 Nov 2026)

## For the 8am presentation

- **New after midnight: the chat is an assistant** (E-55 to E-57).
  - It keeps the conversation, answers from its own knowledge, and reaches into memory only when the model routes
    a question there. Each answer says which: "from memory", "from the model" or "from the web".
  - Qwen3 1.7B and 8B show their reasoning live, then fold it to "Thought for N seconds". The 4B Instruct build
    does not reason.
  - The globe button researches online (Wikipedia), answers with the source, and keeps it on the Research shelf.
  - Drop a PDF, image or video onto the chat, or use the clip. Images and videos are read by Qwen3-VL-4B-Thinking,
    a vision model that reasons. A receipt photo was read line by line, and the 8B answered its total and payment.
  - Memory revises itself: a new price updates the old note, which is tagged superseded and kept as history. A
    repeat is not kept twice.
  - Chats are saved and listed in the sidebar (⌘N for a new one). Stop with ⌘. while it writes. Copy any answer or
    code block. Maths reads as √, ×, ≈.
  - The tensors show while a model fires up, or when you choose to see them (⌘T, or ⌘E for large); otherwise they
    stay hidden.
  - Code streams the step it is writing and lists the files a run wrote; a web page opens in the browser.
- **Memory no longer bloats the SSD (E-54).** Notes are kept at 8 bits: the same answers on the Long Haul (14 and 19
  right at 64K and 256K, against 14 and 20 at 16 bits) in half the disk (18.2 GB against 34.3 GB), first word
  0.094 s. The app's memories were packed in place (`python -m camr_engine.shrink`): 1.7B 34.3 -> 18.2 GB, 4B 44.1
  -> 23.4 GB, 8B 8.6 -> 4.6 GB awake (its other 540 rooms were already asleep). Each reach now has an 8 GB budget:
  the first time the 1.7B or 4B opens, their oldest rooms sleep down to 8 GB and are read as words (the Long Haul
  kept 20 of 40 that way). To keep all 737 awake for the demo, start the app with `CAMR_SHELF_DISK_GB=24`.
- **Code builds café websites from memory (E-58 to E-60).** Six notes about a café (name, colours, menu in KES,
  hours, address, a price rule), then "Build a one-page website for our café: index.html and style.css". Ten rules
  per site, five cafés: with memory the 4B passed 10.0 per site, as good as the notes pasted in the prompt (9.8),
  and the 8B 9.6 (10.0); told ten days back among noise, 9.2 on both; with no memory, 3 and 4 (a working page
  that knows nothing). Before tonight's agent fixes, the 4B with memory said "I don't know." and passed 0.
  Open `v2/docs/examples/cafe/qwen3-4b/index.html` or `qwen3-8b/` to see one. Table:
  `v2/docs/site/benchmarks.md`, "Code: café websites".
- **Demo order:** `apps/mac/demo.txt`. Suggestions on the empty chat start it with one click.
- **Shelves (new at midnight):** memory is now kept on four shelves: Projects (the Long Haul), Coding, Research
  and Personal.
  - "Remember on" Auto files each moment by meaning; or pick a shelf.
  - Every question reads all of them, and the answer names the note and shelf it read, e.g. "note 0 on Coding".
  - When a model loads, its kernels are built and the newest notes are warmed into RAM.
  - Screens: `apps/mac/screens/chat-shelves.png`.
- **Models:** Qwen3 1.7B, 4B and 8B, all three seeded with the Long Haul (737 rooms each), plus Qwen3-VL-4B-Thinking
  as the eyes. The rest are gone, and their records are kept.
- **The app:** `dist/CAMR.app`, a native Mac app with Chat and Code, plus the weights view. Double-click it; it
  starts the engine with Qwen3 4B, whose memory already holds the Long Haul's first 256K tokens (737 rooms).
- **The demo:** type the questions from `apps/mac/demo.txt`, or let the app play them:
  `CAMR_SCRIPT=apps/mac/demo.txt dist/CAMR.app/Contents/MacOS/CAMR`.
  - Who is the Karen landlord? Patrick Chacha.
  - The truck's plate? KDS 711Z, read from room 609 on the SSD, first word in 231 ms.
  - A never-said surname? "I don't know."
  - Remember a new fact, then ask it back.
  - Memory off, the same plate question: "I don't know."
- **The weights view:** ⌘E shows it large beside the chat, for the projector.
  - When the model loads, its 36 layers arrive one by one.
  - With memory on, each answer's room glows, and its notes flow into every layer.
  - Every layer's measured activity moves word by word.
  - With memory off, only the model's layers move.
- **Code:** open `work/demo/kitchen`, then ask "What does vat_cents return for 10,000 cents, and why? Look at
  money.py." It lists the files, reads `money.py`, and answers 1,600 with the half-up rounding.
- **Screens:** `apps/mac/screens/`.
- **Landing page:** `site/`. Preview it with
  `python3 -m http.server 8077 --directory ~/Desktop/camr-build-wt`, then open http://127.0.0.1:8077/site/.
  Nothing is published.

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

**The Mac app** (`apps/mac`, built by `apps/mac/build.sh` into `dist/CAMR.app` with only the command-line tools):
Chat and Code, the weights view, and a model picker (1.7B, 4B or 8B). Each model has its own memory under
`~/.camr/app/<model>/`. `camr_engine.live` reports what the app draws: the weights arriving, the room each answer
reads, and each layer's activity for every word. Swarm is removed. iPhone needs Xcode, which is not installed; the
SwiftUI code is written to carry over.

**The web app** (`python -m camr_engine.app --open`) still has five screens, kept as a fallback; screenshots are in
`v2/docs/screens/`.

| Screen | What it does |
|---|---|
| Models | what fits this Mac (from measured speeds), Hugging Face search and download, MLX and Ollama |
| Chat | memory on/off per session, reach picker, the stage showing SSD → RAM → desk as each answer is made |
| Code | a Claude Code–style agent on your local model: personas, tools, MCP servers, skills, a shell that asks first |
| Memory | every room as a tensor tile, the bus, the RAM ruler, the vault; replays any answer |
| Bench | every record, live: score against history, first word, peak RAM, and Claude's spend |

**The pairing:**
- `camr_engine.pair.ollama` is a proxy that gives Ollama's CLI memory as words (`OLLAMA_HOST=127.0.0.1:11435`).
- `camr serve` is an OpenAI-compatible endpoint with memory (`http://127.0.0.1:11436/v1`), for Ollama, LM Studio,
  OpenCode, curl or any OpenAI SDK.
- Installers are in `packaging/`: `curl | sh`, `uv tool`, npm `camr-memory`, and a Homebrew formula (untested: no
  Homebrew here). See `v2/docs/site/install.md`.

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
| HARP pairs, correction told (60) | 55 | 58 | 28 | **34** |
| HARP pairs, nothing told (60) | 48 | 52 | 21 | 21 |
| BABILong 4k–128k (100) | 78 | — | 39 | 20 |

The Ollama 1.7B has its thinking off, so on HARP it gets the room Claude has to think in (8,192 tokens) to work in
its words (E-43); at 400 tokens 80% of its answers were cut off. With that room, a correction told through the
pairing is worth 13 more right answers (34 against 21), and 6 more than the same correction left in the bare model's 32K window among 30K tokens of noise (28); for Claude it is worth 6 or 7. On BABILong the pairing
hurts (20 against 39): its 512 tokens of notes miss "where is X now", which needs the latest of many mentions.

Claude spend for the night: $28.71 of the $60 cap, logged per call in `v2/records/bench/claude-ledger.jsonl`.

## Multimodal memory (PDFs, photos, charts, videos)

21 files of Mama Njeri's Kitchen (29 planted facts, 8 never-said questions) were told among 99K tokens of the Long
Haul, then asked about after more than 40K tokens of other work (`v2/camr_engine/bench/media_run.py`, E-45).

| Right of 37 | Seed 1 | Seed 2 | First word |
|---|---|---|---|
| **Qwen3 4B + engine**, reading the vision model's words | **37** | **35** | 0.34 s |
| Qwen2.5-VL-3B, the file in its prompt (the upper bound) | 34 | 33 | 1.23 s |
| Ollama qwen2.5vl:3b + pairing (memory as words) | 34 | 33 | 0.22 s |
| Qwen2.5-VL-3B + engine | 33 | 31 | 0.21 s |
| Qwen3 4B bare (newest 64K) | 17 | 18 | 0.32 s |
| Qwen2.5-VL-3B bare (newest 32K) | 0 | 2 | 0.14 s |

- With the engine, the vision model recalls every planted fact (29 of 29), as many as with the file in its prompt.
- Its misses are never-said look-alikes, which it also gets wrong with the file in front of it; the 4B declines them.
- `camr_engine.media.ingest(path, memory, describe=..., day=...)` is what the app calls: it copies the file into the
  vault and remembers each page or frame.

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

- **The engine is not run on the Hugging Face suites.** `suite_run` takes Claude and Ollama only; the engine needs
  a suite wording.
- **LongMemEval, MemoryAgentBench and Web-Bench** have loaders but no runs.
- **Multimodal:** no real photographs, audio, or videos past 12 s. Gemma 3 ran only through Ollama. The 4B ran
  with a 4 GB disk budget (most rooms asleep) because the disk was nearly full (E-46).
- **The thesis document:** being assembled at `docs/thesis/CAMR_Thesis.docx`, chapters 1–6.
- **4M:** rerun on power with the cache cap: 29 of 73 at 3M and at 4M.

## Your calls (taste and vision only)

0. **Empty the Trash.** 511 GB of finished benchmarks' memory folders and the models you dropped are there
   (`~/.Trash/camr-cleared-2026-11-05`), with their records kept in `v2/records/`. Free space comes back once it is
   emptied; I can only move to the Trash, not empty it. `ollama rm qwen2.5vl:3b` frees 3.2 GB more.
1. **The name** is now CAMR everywhere, as you chose. The engine's package is `camr_engine`, because `camr` is the
   old baseline's.
2. **Three small design choices** at the end of `v2/design/DIRECTION.md`:
   - amber or ember for RAM;
   - a flat or a layered stage;
   - Martian Mono or IBM Plex for numbers.
3. **Old branches.** Can I delete `camr-unify` and `Satasdin/camr-overnight-e82a88` on GitHub?
4. **Rotate the Anthropic key** you pasted into chat. It was only ever read from `~/.config/camr/anthropic.env`.
5. **Sleep.** If you ran `sudo pmset -a disablesleep 1`, undo it with `sudo pmset -a disablesleep 0`.

## Look at it

```bash
open ~/Desktop/camr-build-wt/dist/CAMR.app
```

The web app is still there: `cd ~/Desktop/camr-build-wt/v2 && .venv/bin/python -m camr_engine.app --open`.
