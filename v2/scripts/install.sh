#!/bin/sh
# Install and start CAMR on an Apple-silicon Mac (M1 or later), from a fresh download of this repository:
#   sh scripts/install.sh
# It sets up Python with uv, installs CAMR, downloads its two models on first run (about 1.3 GB), runs the health
# check, then opens the app at http://127.0.0.1:8765. Everything stays on the Mac; memory lives in ~/.engram.
set -e
cd "$(dirname "$0")/.."
if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "CAMR needs an Apple-silicon Mac (M1 or later); this machine is $(uname -s) $(uname -m)."; exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (the Python installer CAMR uses)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$PATH"; export PATH
fi
echo "Setting up Python 3.12 and CAMR…"
uv venv --quiet --python 3.12 .venv
uv pip install --quiet --python .venv/bin/python -e .
echo "Health check (the first run downloads the models)…"
.venv/bin/python -m engram.app --check
echo "Starting CAMR. Leave this window open; press Ctrl+C to stop."
exec .venv/bin/python -m engram.app --open
