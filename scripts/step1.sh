#!/bin/sh
# Step 1's runs on this machine: the four baselines (skipped where already done here), engram and engram-words
# through the three proof lives (seed 1), the growth charts, then the speed bench. Restartable. Run it detached:
#   nohup caffeinate -i scripts/step1.sh >> work/step1.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
# wait (at most two hours) for indexing and syncing to settle, so waits measure the contenders and not macOS
n=0
while [ "$(sysctl -n vm.loadavg | awk '{print int($3)}')" -ge 4 ] && [ $n -lt 120 ]; do sleep 60; n=$((n + 1)); done
echo "--- starting $(date), load $(sysctl -n vm.loadavg)"
CONTENDERS="bare perfect camr camr-4b engram engram-words" ./scripts/baselines.sh
.venv/bin/python -I -m engram.ruler speed --persona student 2>&1 | grep -v -i warning
echo "step 1 runs finished $(date)"
