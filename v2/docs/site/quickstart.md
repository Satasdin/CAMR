# Quick start

## What you need

- An Apple-silicon Mac (M1 or later). The engine runs on Apple's MLX. It does not run on Intel Macs, Windows or
  Linux.
- About 2 GB of free disk for the program and its two models, plus room for memory: notes take about 112 KiB per
  token on the 1.7B model (see [Limits](limits.md)).
- An internet connection the first time, to download the models (about 1.3 GB).

## Install

Open Terminal in the repository's `v2` folder and run:

```sh
sh scripts/install.sh
```

The script:
1. checks that this is an Apple-silicon Mac;
2. installs `uv`, the Python installer, if it is missing;
3. sets up Python 3.12 in `.venv` and installs the engine into it;
4. runs a health check, which downloads the two models the first time;
5. builds CAMR for Mac and opens it.

The two models are Qwen3-1.7B (4-bit), which reads and answers, and Qwen3-Embedding-0.6B, which finds the room a
question is about. They live in the Hugging Face cache, `~/.cache/huggingface`.

The health check teaches a throwaway memory two facts and asks about one. It should end with:

```
PASS: CAMR remembered and answered.
```

Each check is kept as a record under `records/health/`.

## Run the app

The install script starts it the first time. After that:

```sh
open mac/build/CAMR.app
```

| Option | Default | What it does |
| --- | --- | --- |
| `--memory DIR` | `~/.camr/default` | the memory folder; it reopens where it left off |
| `--port N` | `8765` | the engine's port (the app picks a free one itself) |
| `--check` | off | run the health check instead of the app, then exit |


The app is one local page. What each screen does is in the [user guide](../USER_GUIDE.md).

The server listens on 127.0.0.1 only. A request must name this host. A POST must be JSON from the app's own page.
Every API call carries a key made when the app starts, which only the served page knows. So other websites open in
the same browser cannot reach your memory.

## Where things are kept

| What | Where |
| --- | --- |
| The app's memory | `~/.camr/default`. Delete the folder to start empty. |
| Simulations | `~/.camr/simulations`, rebuilt each time one starts |
| Reach folders (library sessions) | `~/.camr/session/`, `project/`, `agent/`, `global/` |
| Models | `~/.cache/huggingface` |

## If something goes wrong

| Problem | Fix |
| --- | --- |
| `CAMR needs an Apple-silicon Mac` | This Mac cannot run it: MLX needs M1 or later. |
| The health check says FAIL | Run `.venv/bin/python -m camr_engine.app --check` again. If it keeps failing, delete `~/.cache/huggingface/hub/models--mlx-community--Qwen3-1.7B-4bit` and rerun the installer. |
| The page shows "forbidden" | Reload it. The page gets a fresh key each time the app starts. |

## For developers

```sh
uv pip install --python .venv/bin/python -e ".[dev]"     # pytest
uv pip install --python .venv/bin/python -e ".[bench]"   # the Claude yardstick and the Hugging Face suites
.venv/bin/python -m pytest -q                             # the tests use fakes and load no model
```

Next: use the engine from Python, in [Python library](library.md).
