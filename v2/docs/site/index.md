# The lightweight memory engine

Memory for a language model running on a Mac. The model reads its memory like its own working state, and the
memory moves between the SSD and RAM as each question needs.

## What it is

The engine gives a small local model a memory that grows without making it slower or heavier. What you tell it is
read once by the model. While the model reads, it writes notes to itself inside its layers: its keys and values at
every layer. Those notes are saved to the SSD, in a room of related moments. A question opens the one room it is
about, reads it from the SSD in one burst, and lays it in front of the model already read. The model then reads
only the few closest moments as words, and the question. Everything runs on the Mac with Apple's MLX. Nothing leaves
the machine.

It is not a vector database. The memory is tensors the model reads directly. It has three layers: a small core that
is always in RAM, rooms of saved notes on the SSD, and a vault of plain-text notes that a person can open in
Obsidian. Rooms that are used often stay in RAM. Rooms that fade go to sleep and are kept as words. The app and the
benchmarks exist only to show the engine at work and to measure it. The work is the subject of a thesis: "A
Lightweight External Memory Engine to Bridge the Capability Gap Between On-Device and Cloud Language Models".

Its name is not chosen yet. The code is the Python package `camr`. Earlier write-ups call it CAMR v2.

## The pages

| Page | What it covers |
| --- | --- |
| [Quick start](quickstart.md) | Install with one script, then run the app |
| [The three layers](layers.md) | The core, the rooms and the vault, and how a desk is laid |
| [Reach and the switch](reach.md) | Whose memory a question reads, and turning memory off |
| [RAM, the SSD and sleep](swapping.md) | Where each room's notes are, and what happens when memory outgrows the disk |
| [Python library](library.md) | `Memory` and `Session`: `remember` and `answer`, with their real signatures |
| [Install and integrate](install.md) | `camr` from curl, uv, pipx, Homebrew or npm; the OpenAI-compatible endpoint; OpenCode, LM Studio, Ollama and curl |
| [Pairing with Ollama](ollama.md) | Memory for the `ollama` CLI through a local proxy, and the macOS app's limits |
| [Benchmarks](benchmarks.md) | The Long Haul, the Hugging Face suites, the Claude yardstick, and how to rerun them |
| [Metrics](metrics.md) | What every answer records |
| [Limits](limits.md) | What it does not do yet, stated plainly |

## Measured so far

These come from step 1, on a MacBook Pro M5 Pro with 24 GB, Qwen3-1.7B, three scripted 12-week lives
(DECISIONS.md, E-20):

| | |
| --- | --- |
| Time to the first word | 0.064–0.072 s in every week, flat while memory grew |
| Peak RAM | 1.65–1.83 GB |
| Notes on the SSD | grew from 82 MB to 963 MB |
| Facts known at week 12 | 164 of 255 |

Tonight's results (the Long Haul, the Hugging Face suites, the Claude yardstick, the Ollama pairing): see records.

## For agents

[llms.txt](../../llms.txt) lists these pages. [llms-full.txt](../../llms-full.txt) holds all of them in one file.
