#!/bin/sh
# The 27B on this machine (Qwen3.8-27B-4bit, 16 GB) on the three held-out lives: alone, with CAMR v1, and reading
# CAMR v2's memory as words (its hybrid layers can't use the saved notes). The quiz is asked at week 12 only, the
# week every table compares, then the errands. A quiz already recorded on this machine is skipped. The app is
# stopped first: the 27B needs the RAM.
#   nohup caffeinate -i scripts/big27b.sh >> work/big27b.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
quizzed() {  # a week-12 record of this contender for this life, made on this machine
  $PY -I - "$1" "$2" "$(sysctl -n hw.model)" <<'PYEOF'
import json, pathlib, sys
persona, contender, machine = sys.argv[1:]
for p in pathlib.Path("records").glob(f"*/*-{persona}-s1-{contender}.json"):
    r = json.loads(p.read_text())
    if r["environment"]["machine"] == machine and any(w["week"] == 12 for w in r.get("weeks", [])):
        sys.exit(0)
sys.exit(1)
PYEOF
}
pkill -f "camr_engine.app" || true
echo "--- starting $(date), load $(sysctl -n vm.loadavg)"
for persona in student farmer developer; do
  for c in bare-27b camr-27b camr2-words-27b; do
    if quizzed "$persona" "$c"; then echo "$persona $c: already quizzed"; continue; fi
    $PY -I -m camr_engine.ruler run --persona "$persona" --seed 1 --contender "$c" --quiz-weeks 12 2>&1 | grep -v -i warning
  done
  for c in bare camr camr2-words; do
    $PY -I -m camr_engine.ruler errands --persona "$persona" --seed 1 --contender "$c" --reader 27b 2>&1 | grep -v -i warning
  done
done
echo "27b finished $(date)"
