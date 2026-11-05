#!/bin/zsh
# CAMR.app from the Swift package: a release build, wrapped as an app bundle, signed for this Mac (ad hoc), installed
# as the one CAMR in /Applications, and zipped for the landing page's download. Needs only the command-line tools.
#   apps/mac/build.sh            -> /Applications/CAMR.app, and dist/CAMR.app.zip at the repo root
#   CAMR_NO_INSTALL=1 apps/mac/build.sh   -> only dist/CAMR.app.zip
#
# Only one CAMR.app is ever registered with LaunchServices (so Spotlight and Launchpad show it once): the bundle is
# put together in a temporary folder that Spotlight does not index (.noindex, .metadata_never_index), zipped, copied
# into /Applications with ditto, and the temporary copy is unregistered and removed. No .app is left in dist/.
set -e
HERE="${0:A:h}"  # resolved before the cd below, so a relative path to this script works too
ROOT="${HERE:h:h}"
cd "$HERE"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
INSTALLED=/Applications/CAMR.app

swift build -c release

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/camr-build.XXXXXX.noindex")"
touch "$STAGE/.metadata_never_index"
APP="$STAGE/CAMR.app"
cleanup() {
  [[ -d "$APP" ]] && "$LSREGISTER" -u "$APP" >/dev/null 2>&1 || true
  rm -rf "$STAGE"  # the temporary build folder, made above
}
trap cleanup EXIT

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp .build/release/CAMR "$APP/Contents/MacOS/CAMR"
[[ -f Resources/AppIcon.icns ]] && cp Resources/AppIcon.icns "$APP/Contents/Resources/"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>CAMR</string>
  <key>CFBundleDisplayName</key><string>CAMR</string>
  <key>CFBundleIdentifier</key><string>org.camr.app</string>
  <key>CFBundleExecutable</key><string>CAMR</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.developer-tools</string>
</dict></plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

mkdir -p "$ROOT/dist"
rm -f "$ROOT/dist/CAMR.app.zip"
ditto -c -k --keepParent "$APP" "$ROOT/dist/CAMR.app.zip"
echo "$ROOT/dist/CAMR.app.zip ($(du -sh "$ROOT/dist/CAMR.app.zip" | cut -f1))"

if [[ "${CAMR_NO_INSTALL:-0}" != "1" ]]; then
  running=0
  for pid in $(pgrep -x CAMR); do  # only the installed app counts, not a build run from .build/
    [[ "$(ps -o comm= -p $pid)" == "$INSTALLED/Contents/MacOS/CAMR" ]] && running=1
  done
  if (( running )); then
    echo "CAMR is running from $INSTALLED: quit it, then build again to install." >&2
    exit 1
  fi
  ditto "$APP" "$INSTALLED"  # replaces the installed bundle's files in place
  "$LSREGISTER" -f "$INSTALLED" >/dev/null 2>&1 || true
  echo "$INSTALLED ($(du -sh "$INSTALLED" | cut -f1))"
fi
