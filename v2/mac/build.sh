#!/bin/zsh
# Build CAMR.app from this package: a release build, wrapped in an app bundle with its Info.plist, signed ad hoc
# so macOS will run it from this Mac. The app starts the engine from CAMR_ENGINE_DIR (default: the v2 folder above).
#   mac/build.sh            → mac/build/CAMR.app
#   mac/build.sh --open     → and open it
set -e
cd "$(dirname "$0")"
swift build -c release 2>&1 | grep -vE "search path .* not found" || true
BIN=$(swift build -c release --show-bin-path)/CAMR
[ -x "$BIN" ] || { echo "build failed"; exit 1; }
APP=build/CAMR.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/CAMR"
cp Resources/* "$APP/Contents/Resources/"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>CAMR</string>
  <key>CFBundleDisplayName</key><string>CAMR</string>
  <key>CFBundleIdentifier</key><string>app.camr.mac</string>
  <key>CFBundleExecutable</key><string>CAMR</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

# The engine the app starts, outside macOS's protected folders (Desktop, Documents), so the app never has to ask
# for them: camr_engine copied fresh on every build, its Python environment cloned once (APFS clone: no extra space).
ENGINE="$HOME/Library/Application Support/CAMR/engine"
mkdir -p "$ENGINE"
[ -x "$ENGINE/.venv/bin/python" ] || cp -cR ../.venv "$ENGINE/.venv"
rsync -a --delete --exclude __pycache__ ../camr_engine/ "$ENGINE/camr_engine/"
echo "engine at $ENGINE"
echo "built $(pwd)/$APP"
[ "$1" = "--open" ] && open "$APP"
exit 0
