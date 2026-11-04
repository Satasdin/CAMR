#!/bin/sh
# Builds engram's vendored browser files once: four esbuild bundles from the pinned npm packages, the direct files
# from jsDelivr, each package's licence, and static/vendor/LOCK.json with every file's SHA-256.
#
#   BUILD_DIR=/a/folder/outside/the/repo ./build.sh
#
# npm runs in BUILD_DIR (a fresh temporary folder when not given), so node_modules never sits in the repo. The output
# in ../static/vendor/ is committed; this folder keeps only what rebuilds it (package.json, package-lock.json,
# entries/, build.sh, lock.mjs). Run it again only to change a pin.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../static/vendor"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d -t engram-vendor)}"
mkdir -p "$BUILD_DIR" "$OUT"
cp "$HERE/package.json" "$BUILD_DIR/package.json"
if [ -f "$HERE/package-lock.json" ]; then cp "$HERE/package-lock.json" "$BUILD_DIR/package-lock.json"; fi
rm -rf "$BUILD_DIR/entries" && cp -R "$HERE/entries" "$BUILD_DIR/entries"
cd "$BUILD_DIR"
if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
cp package-lock.json "$HERE/package-lock.json"
for e in ui regl codemirror markdown; do
  ./node_modules/.bin/esbuild "entries/$e.js" --bundle --format=esm --minify --legal-comments=eof \
    --metafile="meta-$e.json" --outfile="$OUT/$e.js"
done
# section A, every licence, the icons module and LOCK.json
node "$HERE/lock.mjs" "$BUILD_DIR" "$OUT"
