#!/bin/zsh
# Builds Burrow.app into app/build.
set -euo pipefail
cd "${0:A:h}"
swift build -c release
bundle=build/Burrow.app
rm -rf "$bundle"
mkdir -p "$bundle/Contents/MacOS"
cp "$(swift build -c release --show-bin-path)/Burrow" "$bundle/Contents/MacOS/Burrow"
cp Info.plist "$bundle/Contents/Info.plist"
codesign --force --sign - "$bundle" >/dev/null
echo "built $PWD/$bundle"
