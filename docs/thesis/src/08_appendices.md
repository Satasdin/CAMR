#! Appendix A: Reproducing the Results

Every number in Chapter 5 comes from a record in `v2/records/bench/2026-11-04/` of the repository, and every record can be made again with the commands below, run from `v2/` on an Apple-silicon Mac after `sh scripts/install.sh`. One measuring job should run at a time (E-35). Claude runs need an Anthropic key in `~/.config/camr/anthropic.env`; every Claude call is held in the ledger against the cap.

Build and inspect the Long Haul, and grade any answers:

```
.venv/bin/python -m camr_engine.bench.haul build --seed 1 --out work/haul/s1
.venv/bin/python -m camr_engine.bench.longhaul show --dir work/haul/s1
.venv/bin/python -m camr_engine.bench.haul grade --dir work/haul/s1 --answers answers.jsonl --cut 1M
```

Run the engine, a bare model, Ollama and Claude on the Long Haul:

```
.venv/bin/python -m camr_engine.bench.local longhaul --contender engine:qwen3-4b --dir work/haul/s1
.venv/bin/python -m camr_engine.bench.local longhaul --contender bare:qwen3-4b --dir work/haul/s1
.venv/bin/python -m camr_engine.bench.ollama_run longhaul --contender ollama:qwen3-1.7b --dir work/haul/s1
.venv/bin/python -m camr_engine.bench.longhaul claude --model claude-sonnet-5-5 --dir work/haul/s1
```

Measure the wait as memory grows, and how fast each model reads and writes on this Mac:

```
.venv/bin/python -m camr_engine.bench.local speed --contender engine:qwen3-1.7b --dir work/haul/s1
.venv/bin/python -m camr_engine.bench.throughput --out records/bench
```

Run the public suites:

```
.venv/bin/python -m camr_engine.bench.suite_run babilong --contender ollama-bare:qwen3:1.7b --n 20
.venv/bin/python -m camr_engine.bench.suite_run harp --contender ollama:qwen3-1.7b --n 20
.venv/bin/python -m camr_engine.bench.suite_run math500 --contender claude-haiku-5-5 --n 50 --max-usd 10
```

Table {tab:records} lists the records behind each result.

Rebuild this report's charts and diagrams, and the report itself, from the repository root:

```
python docs/thesis/figures/src/make_charts.py
python docs/thesis/diagrams/src/final_diagrams.py
python docs/thesis/build_thesis.py
```

Table: {#records} The records behind Chapter 5 (`v2/records/bench/2026-11-04/`)

| Result | Record files |
|---|---|
| The 4B with CAMR, 64K to 2M; 3M without and with the cap; 3M and 4M | `071525-longhaul-engine-qwen3-4b.json`; `100255-…`; `143706-longhaul-engine-qwen3-4b.json` |
| The 4B alone | `092854-longhaul-bare-qwen3-4b.json`; `155141-longhaul-bare-qwen3-4b.json` |
| The 8B with CAMR and alone | `161208-longhaul-engine-qwen3-8b.json`; `171043-longhaul-bare-qwen3-8b.json` |
| The 27B with the memory as words | `172930-longhaul-words-qwen-27b.json` |
| The 1.7B, both wordings, with CAMR and alone | `044359-…`, `062857-…`, `051530-…`, `070454-longhaul-*-qwen3-1.7b*.json` |
| Ollama on the Long Haul | `053819-longhaul-ollama-qwen3-1.7b.json`; `052439-longhaul-ollama-bare-qwen3-1.7b.json` |
| Claude on the Long Haul | `022518-…`, `022717-…`, `023106-…`, `094146-…`, `094325-claude-*-longhaul.json` |
| Speed as memory grows | `055344-speed-engine-qwen3-1.7b.json` |
| Storage at 16, 8 and 4 bits (5 November) | `003939-…-16bit.json`, `004714-…-8bit-8GB.json`, `004321-…-4bit.json` |
| Reach | `195128-…`, `195633-…`, `200137-…`, `201043-reach-engine-qwen3-4b-*.json` |
| The suites | `*-math500-*`, `*-aime-*`, `*-harp-*`, `*-babilong-*.json` |
| Claude's spending | `v2/records/bench/claude-ledger.jsonl` |

#! Appendix B: Decision Log Entries Cited

The project's decision log (`v2/DECISIONS.md`) records every technical decision with its reason and evidence. Table {tab:decisions} lists the entries this report cites.

Table: {#decisions} Decision log entries cited in this report

| Entry | Decision |
|---|---|
| E-02 | One reader and one embedder for every contender, so differences between contenders are differences between memories |
| E-05 | Three scripted twelve-week lives, generated from a persona and a seed |
| E-08 | Growth measured as facts known out of those told; false memories counted apart |
| E-10 | Deterministic answers: greedy decoding, thinking off |
| E-12 | Every record carries the machine, the versions and a hash of the code |
| E-14 | Honest SSD reads: room files read with the file cache bypassed |
| E-15 | A room is written as one continuous page |
| E-16 | One room on the desk, plus the closest moments as words |
| E-17 | A new machine: the MacBook Pro M5 Pro, with the MacBook Air's results kept |
| E-18 | Room size and how many moments to re-read, tuned on development lives |
| E-19 | Step 1's pass marks, written before any held-out run |
| E-20 | Step 1's results against its pass marks |
| E-21 | What "used" means, and what watching attention costs |
| E-24 | The first app: a local page with its security checks |
| E-25 | The errands, measured |
| E-26 | A model sixteen times bigger on the same Mac, reading the memory as words |
| E-27 | A crash window in the room files, and its fix |
| E-29 | The engine is the project: three layers, reach, local only, Claude only as a yardstick |
| E-30 | The Long Haul, the study's own hard test |
| E-31 | Asking never teaches |
| E-32 | Everyone reads the same instructions |
| E-33 | Ollama pairs through a proxy |
| E-34 | The app's visual design, "Instrument" |
| E-35 | One measuring job at a time |
| E-36 | The Hugging Face suites run on Claude and Ollama, not yet on the engine |
| E-37 | The 1.7B's wording, not its memory, sank its recall at 1M and 2M |
| E-38 | Speed does not grow with memory |
| E-39 | Past 2M: the same questions under one and two million more tokens |
| E-40 | The engine's process held 19 GB; MLX's buffer cache capped at 1 GB |
| E-41 | The cap, measured: a third of the RAM, almost twice the speed, the same answers |
| E-42 | Project reach is the best reach |
| E-43 | The Ollama suite runs redone where the runner, not the model, set the score |
| E-44 | Files into memory: a vision model turns them into words once |
| E-47 | An OpenAI-compatible endpoint with memory |
| E-48 | One `camr` command and its installers |
| E-49 | The landing page and the meaning of colour |
| E-50 | Swarm removed: the app is Chat and Code |
| E-51 | Shelves: memory kept apart by kind of work (Projects, Coding, Research, Personal), and read as one |
| E-52 | Warm before the first question: kernels built, newest rooms read into RAM |
| E-55 | The chat is an assistant, and the model decides when to reach into memory |
| E-56 | Memory that revises itself, never by deleting |
| E-57 | Eyes: a vision model that also reasons (Qwen3-VL-4B-Thinking) |
