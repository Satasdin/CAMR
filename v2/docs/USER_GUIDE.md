# CAMR user guide

CAMR is a memory for a small language model that runs entirely on a Mac. What you tell it is saved to the Mac's
SSD as the model's own notes. Later questions open the part of memory they are about, so it answers from what it
was told without getting slower as memory grows. Nothing leaves the machine.

## What you need

- An Apple-silicon Mac (M1 or later). CAMR uses Apple's MLX and does not run on Intel Macs, Windows or Linux.
- About 2 GB of free disk space for the program and its two models, plus about 3 MB per moment remembered.
- An internet connection the first time only, to download the models (about 1.3 GB).

## Install and start

Open Terminal in the downloaded folder and run:

```sh
sh scripts/install.sh
```

It checks the Mac, sets up Python, installs CAMR, downloads the models, runs a health check, and opens CAMR in
the browser at http://127.0.0.1:8765. The health check should end with `PASS: CAMR remembered and answered.`
Leave the Terminal window open while you use CAMR; press Ctrl+C there to stop it.

To start it again later:

```sh
.venv/bin/python -m camr_engine.app --open
```

## The four tabs

| Tab | What to do | What it shows |
|---|---|---|
| **Simulation** | Pick a life and press **Start** | 12 weeks of a scripted life arriving day by day in about 90 seconds. Each moment becomes a red cell. Each week the same 25 questions are asked, and the moments each answer leans on glow green. The charts show facts known climbing while the wait and the memory in use stay flat. |
| **Chat** | Type a fact ("My sister Amina moved to Nakuru."), then a question ending in "?" ("Where does my sister live?") | It remembers statements and answers questions from memory. **Look inside** opens that answer in Brain. |
| **Errands** | Give it a task ("Set a reminder for my neighbour's birthday.") | An agent with ten pretend tools. CAMR fills in the tool's details from memory and shows the call it made. |
| **Brain** | Pick any answer or errand; press **Play** | The answer replayed word by word over the memory: red cells are moments, white rings were picked up, green glow is what each word leaned on. The traces strip below has one row per moment. **Went wrong** shows the mistakes from a quizzed life. |

To try Chat, Errands and Brain on a whole life, press **Load life** in the Chat tab, then **Ask its 100
questions** or **Give it 100 errands**. Each takes under a minute.

## A five-minute demonstration

1. **Simulation.** Choose the dairy-cooperative manager on the held-out life and press Start. While it runs:
   - every red cell is something the farmer said;
   - cells sharing a lobe share a room on the SSD;
   - each week the green glow is the quiz being answered;
   - the knows line climbs while the wait (about 0.07 s) and the memory (about 1.8 GB) do not.
2. **Chat.** Teach it one fact about yourself, ask about it, and press **Look inside**.
3. **Errands.** Ask for a reminder for someone's birthday. The date in the tool call came from memory.
4. **Brain → Went wrong.** Open a "Made it up" errand and press Play. The glow shows which moments it leaned on
   when it guessed. That is the known weakness: the small model never asks when it doesn't know.

## Where things are kept

- **Your memory:** `~/.camr/default` holds room files, an index, and `events.jsonl`, the log the Brain tab reads.
  Delete this folder to start with an empty memory.
- **Simulations:** `~/.camr/simulations`, rebuilt each time a simulation starts.
- **Models:** the Hugging Face cache, `~/.cache/huggingface`.

## If something goes wrong

| Problem | Fix |
|---|---|
| `CAMR needs an Apple-silicon Mac` | This Mac can't run it; MLX needs M1 or later. |
| The health check says FAIL | Run it again with `.venv/bin/python -m camr_engine.app --check`. If it keeps failing, the model download may be incomplete: delete `~/.cache/huggingface/hub/models--mlx-community--Qwen3-1.7B-4bit` and rerun the installer. |
| The page shows "forbidden" | Reload it. The page gets a fresh key each time CAMR starts. |
| Port 8765 is busy | Start it on another port: `.venv/bin/python -m camr_engine.app --open --port 8790`. |

## For assessors: reproducing the measurements

The evaluation code is under `camr_engine/ruler`. Every run writes a test record to `records/`, naming the machine and
the code that made it. `scripts/step1.sh` reruns every contender on the three held-out lives and `scripts/errands.sh`
reruns the agent use case. Comparing against the first version of CAMR needs that repository too; the README says
how. The test suite runs with `.venv/bin/python -m pytest` after `uv pip install -e ".[dev]"`.
