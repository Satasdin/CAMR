#!/bin/sh
# CAMR, the memory engine, on an Apple-silicon Mac:
#   curl -fsSL https://raw.githubusercontent.com/Satasdin/CAMR/camr-build/packaging/install.sh | sh
# It installs the engine into an environment of its own (~/.camr/engine) and links the `camr` command into
# ~/.local/bin. It uses uv when uv is installed, else python3 -m venv (Python 3.11 or newer). Nothing else on the Mac
# changes, and running it again updates the engine. Memory lives in ~/.camr/default; the models (about 1.3 GB) are
# downloaded on first use.
#   CAMR_SOURCE  what to install: a pip requirement, or a local folder holding pyproject.toml (default: the
#                camr-build branch on GitHub, folder v2)
#   CAMR_HOME    where the engine goes (default ~/.camr)
#   CAMR_BIN     where the command is linked (default ~/.local/bin)
set -eu

SOURCE="${CAMR_SOURCE:-camr-engine @ git+https://github.com/Satasdin/CAMR.git@camr-build#subdirectory=v2}"
CAMR_HOME="${CAMR_HOME:-$HOME/.camr}"
ENV="$CAMR_HOME/engine"
BIN="${CAMR_BIN:-$HOME/.local/bin}"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  fail "CAMR runs its models with MLX on an Apple-silicon Mac (M1 or later); this is $(uname -s) $(uname -m)."
fi
[ -d "$SOURCE" ] && SOURCE="$(cd "$SOURCE" && pwd)"  # a local folder, as an absolute path

UV=""
for c in uv "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
  if command -v "$c" >/dev/null 2>&1; then UV="$(command -v "$c")"; break; fi
done

mkdir -p "$CAMR_HOME" "$BIN"
if [ -n "$UV" ]; then
  say "Installing CAMR with uv ($UV) into $ENV"
  [ -x "$ENV/bin/python" ] || "$UV" venv --quiet --python 3.12 "$ENV"
  "$UV" pip install --quiet --python "$ENV/bin/python" --reinstall-package camr-engine "$SOURCE"
else
  PY=""
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
      PY="$("$c" -c 'import os, sys; print(os.path.realpath(sys.executable))')"; break  # not a link: venv needs its home
    fi
  done
  [ -n "$PY" ] || fail "CAMR needs Python 3.11 or newer (https://www.python.org/downloads/), or uv (https://docs.astral.sh/uv/)."
  say "Installing CAMR with $($PY --version) into $ENV"
  [ -x "$ENV/bin/python" ] || "$PY" -m venv "$ENV"
  "$ENV/bin/python" -m pip install --quiet --upgrade pip
  "$ENV/bin/python" -m pip install --quiet --upgrade "$SOURCE"
  "$ENV/bin/python" -m pip install --quiet --force-reinstall --no-deps "$SOURCE"  # the newest engine, same version
fi
[ -x "$ENV/bin/camr" ] || fail "the install finished without a camr command in $ENV/bin"

if [ -e "$BIN/camr" ] && [ "$(readlink "$BIN/camr" 2>/dev/null)" != "$ENV/bin/camr" ]; then
  say "Replacing $BIN/camr (it pointed at $(readlink "$BIN/camr" 2>/dev/null || echo 'a file'))"
fi
ln -sf "$ENV/bin/camr" "$BIN/camr"
say "Installed $("$ENV/bin/camr" version): $BIN/camr"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) say "Add $BIN to your PATH:  echo 'export PATH=\"$BIN:\$PATH\"' >> ~/.zprofile  (then open a new terminal)";;
esac
cat <<EOF

  camr doctor                      what is installed and what is listening
  camr serve --backend ollama      an OpenAI-compatible endpoint with memory, at http://127.0.0.1:11436/v1
  camr ollama                      memory for the ollama CLI: OLLAMA_HOST=127.0.0.1:11435 ollama run qwen3:1.7b

EOF
