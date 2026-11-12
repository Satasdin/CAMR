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
# The burrow command rides inside the app, so the Programs page can point every program at a full path that exists.
(cd .. && swift build -c release --product burrow)
mkdir -p "$bundle/Contents/Resources/bin"
cp "$(cd .. && swift build -c release --show-bin-path)/burrow" "$bundle/Contents/Resources/bin/burrow"
codesign --force --sign - "$bundle" >/dev/null
echo "built $PWD/$bundle"
