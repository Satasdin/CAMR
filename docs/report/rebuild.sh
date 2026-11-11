#!/bin/zsh
# Rebuilds the report end to end and refreshes the showcase folder.
#   docs/report/rebuild.sh
# 1. builds Burrow_Report_Word.docx from chapters4/
# 2. opens it in Word, updates every field and list, exports check-word.pdf, closes it
# 3. copies both to the submission names
# 4. refreshes ~/FINAL YEAR PROJECT (report, app, terminal program, installer)
set -euo pipefail
here="${0:A:h}"; repo="${here:h:h}"; cd "$here"
name=IbrahimSudheysi_166344_TiberiusTabulu
showcase="$HOME/FINAL YEAR PROJECT"

# Refuse to overwrite the submission copy if it was edited by hand after the last build.
if [[ -f Burrow_Report_Word.docx && -f $name.docx ]] && ! cmp -s Burrow_Report_Word.docx $name.docx; then
  echo "$name.docx differs from the last build (edited in Word?). Copy your changes into the source first." >&2
  exit 1
fi

/usr/bin/python3 build_word.py

open -a "Microsoft Word" "$here/Burrow_Report_Word.docx"
for _ in {1..30}; do
  [[ "$(osascript -e 'tell application "Microsoft Word" to return name of active document' 2>/dev/null)" == Burrow_Report_Word.docx ]] && break
  sleep 1
done
[[ "$(osascript -e 'tell application "Microsoft Word" to return name of active document')" == Burrow_Report_Word.docx ]] \
  || { echo "Word did not bring the new build to the front; nothing was exported." >&2; exit 1; }
osascript word_update.applescript "$here/check-word.pdf" >/dev/null
osascript -e 'tell application "Microsoft Word" to close active document saving no'

cp Burrow_Report_Word.docx $name.docx
cp check-word.pdf $name.pdf

mkdir -p "$showcase/1 Report" "$showcase/2 Application"
cp $name.docx $name.pdf "$showcase/1 Report/"
(cd "$repo" && swift build -c release --product burrow >/dev/null)
cp "$repo/.build/release/burrow" "$showcase/2 Application/burrow"
cp "$repo/scripts/install.sh" "$showcase/2 Application/install.sh"
if [[ -d "$repo/app/build/Burrow.app" ]]; then
  rm -rf "$showcase/2 Application/Burrow.app"
  ditto "$repo/app/build/Burrow.app" "$showcase/2 Application/Burrow.app"
fi
echo "Report rebuilt and copied to $showcase"
