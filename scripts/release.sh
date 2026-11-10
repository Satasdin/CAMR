#!/bin/zsh
# Builds the terminal program and the desktop app and publishes them as a GitHub release.
#   scripts/release.sh v1.0.0
set -euo pipefail
cd "${0:A:h}/.."
version="${1:?usage: release.sh vX.Y.Z}"
tag="burrow-$version"
out="$(mktemp -d)"

swift build -c release --product burrow
cp .build/release/burrow "$out/burrow"
codesign --force --sign - "$out/burrow"
tar -czf "$out/burrow-macos-arm64.tar.gz" -C "$out" burrow

app/build.sh
ditto -c -k --sequesterRsrc --keepParent app/build/Burrow.app "$out/Burrow-macos-arm64.zip"

cp scripts/install.sh "$out/install.sh"
(cd "$out" && shasum -a 256 burrow-macos-arm64.tar.gz Burrow-macos-arm64.zip install.sh > SHA256SUMS)

gh release create "$tag" -R Satasdin/CAMR --target "$(git rev-parse HEAD)" --latest \
  --title "Burrow $version" \
  --notes "Burrow for macOS 14 or later on Apple silicon. Install the terminal version with: curl -fsSL https://github.com/Satasdin/CAMR/releases/latest/download/install.sh | sh" \
  "$out/burrow-macos-arm64.tar.gz" "$out/Burrow-macos-arm64.zip" "$out/install.sh" "$out/SHA256SUMS"
echo "published $tag"
