#!/bin/sh
# Installs Burrow from its latest GitHub release.
#   curl -fsSL https://github.com/Satasdin/CAMR/releases/latest/download/install.sh | sh
#   ... | sh -s -- --app     also installs the desktop application
set -eu

BASE="https://github.com/Satasdin/CAMR/releases/latest/download"
BIN_DIR="${BURROW_BIN_DIR:-$HOME/.local/bin}"
WITH_APP=0
for arg in "$@"; do
  case "$arg" in
    --app) WITH_APP=1 ;;
    *) echo "burrow: unknown option $arg" >&2; exit 2 ;;
  esac
done

fail() { echo "burrow: $1" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || fail "this release is for macOS only."
[ "$(uname -m)" = "arm64" ] || fail "this release is for Apple silicon only."
major="$(sw_vers -productVersion | cut -d. -f1)"
[ "$major" -ge 14 ] || fail "macOS 14 or later is required."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fetch() {
  curl -fsSL "$BASE/$1" -o "$tmp/$1" || fail "could not download $1."
  expected="$(grep " $1\$" "$tmp/SHA256SUMS" | cut -d' ' -f1)"
  [ -n "$expected" ] || fail "no checksum for $1."
  actual="$(shasum -a 256 "$tmp/$1" | cut -d' ' -f1)"
  [ "$expected" = "$actual" ] || fail "the checksum of $1 does not match."
}

curl -fsSL "$BASE/SHA256SUMS" -o "$tmp/SHA256SUMS" || fail "could not reach the release."

fetch burrow-macos-arm64.tar.gz
mkdir -p "$BIN_DIR"
tar -xzf "$tmp/burrow-macos-arm64.tar.gz" -C "$tmp"
install -m 755 "$tmp/burrow" "$BIN_DIR/burrow"
echo "Installed $BIN_DIR/burrow"

if [ "$WITH_APP" = 1 ]; then
  fetch Burrow-macos-arm64.zip
  if [ -n "${BURROW_APP_DIR:-}" ]; then app_dir="$BURROW_APP_DIR"
  elif [ -w /Applications ]; then app_dir=/Applications
  else app_dir="$HOME/Applications"; fi
  mkdir -p "$app_dir"
  rm -rf "$app_dir/Burrow.app"
  ditto -x -k "$tmp/Burrow-macos-arm64.zip" "$app_dir"
  echo "Installed $app_dir/Burrow.app"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Add it to your path:  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
command -v ollama >/dev/null 2>&1 || echo "Burrow reads with local models through Ollama: https://ollama.com"
echo "Next:  ollama pull qwen3-embedding:0.6b  and a chat model, then  burrow index <folder> --vault"
