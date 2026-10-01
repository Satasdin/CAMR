#!/usr/bin/env bash
# CAMR Personal installer for macOS and Linux.
#   curl -fsSL https://raw.githubusercontent.com/Satasdin/CAMR/main/install/install.sh | bash
# Installs CAMR into its own virtual environment (~/.camr/venv) and puts a `camr` command in ~/.local/bin.
# Nothing else on your system is changed. Your memory lives in ~/.camr/memory.sqlite.
set -euo pipefail

REF="${CAMR_REF:-main}"                       # branch or tag to install
SRC="git+https://github.com/Satasdin/CAMR.git@${REF}"
HOME_DIR="${CAMR_HOME:-$HOME/.camr}"
BIN_DIR="$HOME/.local/bin"

say() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31merror:\033[0m %s\n" "$*" >&2; exit 1; }

# 1. Python 3.10+
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.10 or newer is required (https://www.python.org/downloads/)."
say "Using $($PY --version)"

# 2. Private virtual environment
mkdir -p "$HOME_DIR" "$BIN_DIR"
"$PY" -m venv "$HOME_DIR/venv"
"$HOME_DIR/venv/bin/python" -m pip install --quiet --upgrade pip
if [ "$(uname -s)" = "Linux" ] && [ "${CAMR_TORCH:-cpu}" = "cpu" ]; then
  # The embedder runs on CPU; the CPU build of PyTorch is ~200 MB instead of several GB of CUDA libraries.
  say "Installing CPU PyTorch (set CAMR_TORCH=cuda to skip)"
  "$HOME_DIR/venv/bin/python" -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
fi
say "Installing CAMR ($REF). The first install downloads the embedder's libraries; this can take a few minutes."
"$HOME_DIR/venv/bin/python" -m pip install --quiet "camr[app] @ ${SRC}"
ln -sf "$HOME_DIR/venv/bin/camr" "$BIN_DIR/camr"
say "Installed: $BIN_DIR/camr"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) say "Add $BIN_DIR to your PATH, e.g.  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc";; esac

# 3. Ollama (the model runtime) is separate: we only check for it.
if command -v ollama >/dev/null 2>&1; then
  say "Ollama found. Models you already have:"; ollama list || true
else
  say "Ollama is not installed. Get it from https://ollama.com/download, then:  ollama pull qwen2.5:1.5b"
fi

say "Done. Start CAMR Personal with:   camr app"
