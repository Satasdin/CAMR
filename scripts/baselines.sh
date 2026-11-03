#!/bin/sh
# Contenders through the three proof lives (seed 1), then the growth charts. CONTENDERS picks which (default: the
# four baselines). About 90 minutes per life on a MacBook Air M4; run it on the charger. A run that already has a complete record made
# on this machine is skipped, so the script can be restarted after an interruption.
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python

complete() {  # a finished record of this run, made on this machine
  $PY -I - "$1" "$2" "$(sysctl -n hw.model)" <<'EOF'
import json, pathlib, sys
persona, contender, machine = sys.argv[1:]
for p in pathlib.Path("records").glob(f"*/*-{persona}-s1-{contender}.json"):
    r = json.loads(p.read_text())
    if len(r.get("weeks", [])) == r.get("weeks_planned") and r["environment"]["machine"] == machine:
        sys.exit(0)
sys.exit(1)
EOF
}

for persona in student farmer developer; do
  for contender in ${CONTENDERS:-bare perfect camr camr-4b}; do
    if complete "$persona" "$contender"; then
      echo "$persona $contender: already complete"
      continue
    fi
    $PY -I -m engram.ruler run --persona "$persona" --seed 1 --contender "$contender" 2>&1 | grep -v -i warning
  done
  $PY -I -m engram.ruler chart --persona "$persona" --seed 1
done
echo "runs finished"
